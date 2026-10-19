"""
pten.fs_doc
~~~~~~~~~~~

飞书文档（docx）的高层封装：文档的创建与读取、文本 / markdown 追加、
末尾文本块删除；另含云空间文件夹的文件清单查询。鉴权由 FsCorpApi 的
tenant_access_token 经 Authorization 请求头完成。
"""

import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from . import logger
from .fs_api import CORP_API_TYPE, FsCorpApi, fetch_all_pages, sub_url
from .keys import Keys


class FsDoc:
    """飞书文档客户端，封装常用文档读写操作。

    :param keys_filepath: 配置文件路径，缺省按 Keys 的查找链解析（见 :class:`pten.keys.Keys`）
    :param keys: 共享 Keys 实例，可跨模块注入以复用 token 缓存
    """

    # append_markdown 的单次「创建嵌套块」插入上限（官方限制：descendants 与 children_id 各 1-1000）
    _CONVERT_INSERT_LIMIT = 1000
    # _read_image 下载外部图片的超时秒数，避免单个挂起的图片源阻塞整次追加
    _IMAGE_DOWNLOAD_TIMEOUT = 30
    # 编辑类请求（创建块 / 创建嵌套块 / 更新块 / 删除块）的最小间隔秒数：官方限频
    # 为每秒 3 次（应用级超限返回 400/99991400，单篇文档级超限返回 429）
    _DOCX_EDIT_INTERVAL = 0.34

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
        self.keys = keys if keys else Keys(keys_filepath)
        self.api = FsCorpApi(keys_filepath, keys=keys)
        # 最近一次编辑类请求的时间戳；初始值 0 保证首个请求不等待
        self._last_edit_time = 0.0

    def _pace_docx_edit(self):
        """编辑类请求（创建块 / 创建嵌套块 / 更新块 / 删除块）前节流，避免撞官方每秒 3 次的编辑限频。"""
        wait = self._DOCX_EDIT_INTERVAL - (time.monotonic() - self._last_edit_time)
        if wait > 0:
            time.sleep(wait)
        self._last_edit_time = time.monotonic()

    def create_document(self, title=None, folder_token=None, **kwargs):
        """创建一篇文档（空文档，不支持带内容创建；要基于模板创建需走 drive 复制文件接口）。

        :param title: 文档标题（纯文本，1-800 字符），缺省由服务端命名
        :param folder_token: 归属文件夹 token，缺省创建在云空间根目录
            （tenant_access_token 仅能指定应用创建的文件夹）
        :return: data.document 含 document_id / revision_id / title；
            document_id 可拼出文档链接 ``https://<域名>/docx/<document_id>``
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create
        """
        data = {}
        if title:
            data["title"] = title
        if folder_token:
            data["folder_token"] = folder_token
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["DOC_CREATE"], data)

    def get_document(self, document_id, **kwargs):
        """获取文档基本信息。

        :param document_id: 文档 token（27 字符；知识库内的文档 URL token
            并非 document_id，需先经 wiki 节点接口换取 obj_token）
        :return: data.document 含 document_id / revision_id / title /
            display_setting / cover
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/get
        """
        shortUrl, method = CORP_API_TYPE["DOC_GET"]
        url = sub_url(shortUrl, DOCUMENT_ID=document_id)
        return self.api.http_call([url, method], kwargs)

    def get_raw_content(self, document_id, **kwargs):
        """获取文档纯文本内容（不含富文本结构，段落以 ``\\n`` 分隔）。

        :param document_id: 文档 token
        :return: data.content 为文档纯文本字符串
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/raw_content
        """
        shortUrl, method = CORP_API_TYPE["DOC_RAW_CONTENT"]
        url = sub_url(shortUrl, DOCUMENT_ID=document_id)
        return self.api.http_call([url, method], kwargs)

    def list_blocks(
        self,
        document_id,
        fetch_all=True,
        page_size=None,
        page_token=None,
        document_revision_id=None,
        **kwargs,
    ):
        """列出文档中的所有块（含根 page 块与全部嵌套子块），默认自动翻页返回全部块。

        根 page 块的 block_id 即 document_id，其 children 为顶层块的有序 block_id 列表
        （删除末尾块等按位置操作依赖此顺序）。

        :param document_id: 文档 token
        :param fetch_all: True（默认）自动翻页，聚合全部块后返回响应 dict
            （data.items 为全量块，data.has_more=False，data.total 为实际返回数）；
            False 只查一页，返回原始响应 dict（data 含 items / has_more / page_token），
            翻页控制权在调用方
        :param page_size: 分页大小，最大 500；fetch_all=True 缺省 500（API 上限，
            最小化请求次数），False 缺省不传（服务端默认 500）
        :param page_token: 起始分页标记，缺省从头遍历；fetch_all=True 时从该标记处继续聚合
        :param document_revision_id: 文档版本号，缺省 -1（服务端默认，最新版本）
        :return: 始终返回响应 dict（fetch_all=True 时 data.items 为聚合后的全量块、
            data.has_more=False；False 时为单页原始响应）
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/list
        """

        def get_page(page_size, page_token):
            shortUrl, method = CORP_API_TYPE["DOC_BLOCK_LIST"]
            url = sub_url(shortUrl, DOCUMENT_ID=document_id)
            args = {}
            if page_size is not None:
                args["page_size"] = str(page_size)
            if page_token:
                args["page_token"] = page_token
            if document_revision_id is not None:
                args["document_revision_id"] = str(document_revision_id)
            args.update(kwargs)
            return self.api.http_call([url, method], args)

        if not fetch_all:
            # 单页模式：返回原始响应，翻页控制权在调用方
            return get_page(page_size, page_token)
        return fetch_all_pages(get_page, page_size, page_token, 500)

    def list_folder_files(
        self,
        folder_token=None,
        fetch_all=True,
        page_size=None,
        page_token=None,
        order_by=None,
        direction=None,
        user_id_type=None,
        **kwargs,
    ):
        """获取文件夹中的文件清单（仅当前层级，不递归子文件夹）。

        条目含名称 / 类型 / token / url / 创建与修改时间 / 所有者 ID，shortcut
        条目另带 shortcut_info 指向原文件。根目录（不传 folder_token 或传空串）
        一次返回全部，不支持分页、不返回快捷方式。

        :param folder_token: 文件夹 token，缺省或空串为云空间根目录
        :param fetch_all: True（默认）自动翻页，聚合全部文件后返回响应 dict
            （data.files 为全量文件，data.has_more=False，data.total 为实际返回数）；
            False 只查一页，返回原始响应 dict（data 含 files / has_more /
            next_page_token），翻页控制权在调用方
        :param page_size: 分页大小，最大 200；fetch_all=True 缺省 200（API 上限，
            最小化请求次数），False 缺省不传（服务端默认 100）
        :param page_token: 起始分页标记，缺省从头遍历；fetch_all=True 时从该标记处继续聚合
        :param order_by: 排序字段，EditedTime（服务端默认）/ CreatedTime
        :param direction: 排序方向，ASC 升序 / DESC 降序
        :param user_id_type: owner_id 的用户 ID 类型，open_id（服务端默认）/
            union_id / user_id
        :return: 始终返回响应 dict（fetch_all=True 时 data.files 为聚合后的全量文件、
            data.has_more=False；False 时为单页原始响应）
        https://open.feishu.cn/document/server-docs/docs/drive-v1/folder/list
        """

        def get_page(page_size, page_token):
            args = {}
            if folder_token:
                args["folder_token"] = folder_token
                # 根目录不支持分页，分页参数仅在指定文件夹时拼接
                if page_size is not None:
                    args["page_size"] = str(page_size)
                if page_token:
                    args["page_token"] = page_token
            if order_by:
                args["order_by"] = order_by
            if direction:
                args["direction"] = direction
            if user_id_type:
                args["user_id_type"] = user_id_type
            args.update(kwargs)
            return self.api.http_call(CORP_API_TYPE["FOLDER_FILE_LIST"], args)

        if not fetch_all:
            # 单页模式：返回原始响应，翻页控制权在调用方
            return get_page(page_size, page_token)
        return fetch_all_pages(
            get_page,
            page_size,
            page_token,
            200,
            items_key="files",
            token_key="next_page_token",
        )

    def append_text(self, document_id, text, **kwargs):
        """把一段纯文本作为一个文本块插入到文档末尾。

        多行文本（含 ``\\n``）整体进同一个文本块，``\\n`` 以软换行（同段落内换行）呈现；
        需要每行独立成段时改用 :meth:`append_markdown`。index 不传，服务端默认 -1
        （插入父块 children 末尾）。

        :param document_id: 文档 token
        :param text: 待插入的纯文本；为空或全空白时不发请求，返回 ``{"code": -1}`` 错误 dict
        :return: data.children 为新建的块（含服务端生成的 block_id），及 document_revision_id
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/create
        """
        if not text or not text.strip():
            msg = "待插入的文本不能为空"
            logger.error(msg)
            return {"code": -1, "msg": msg}
        block = {
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": text}}], "style": {}},
        }
        shortUrl, method = CORP_API_TYPE["DOC_BLOCK_CREATE"]
        # 文档根块的 block_id 即 document_id：对根块创建子块 = 插入到文档顶层末尾
        url = sub_url(shortUrl, DOCUMENT_ID=document_id, BLOCK_ID=document_id)
        data = {"children": [block]}
        data.update(kwargs)
        self._pace_docx_edit()
        return self.api.http_call([url, method], data)

    def append_markdown(self, document_id, markdown, base_dir=None):
        """把 markdown 文本转换为文档块后插入到文档末尾。

        两步流程（官方规定）：先调 convert 全局端点（只转换、不修改文档）得到带
        临时 block_id 的块树；再把 ``first_level_block_ids`` 作为 ``children_id``、
        ``blocks``（剥离 Table 块的只读字段 merge_info）作为 ``descendants``，对
        文档根块调「创建嵌套块」（index 缺省 -1 = 插入末尾）。转换出的块超过 1000
        时按顶层子树分批插入；多批时返回最后一批的插入响应。插入与图片回填都是
        编辑操作，自动按最小间隔节流（0.34 秒），避免撞官方每秒 3 次的编辑限频。
        单个顶层块子树自身超过 1000 块（如超大表格）时无法分批，抛 ``ValueError``
        ——拆分 markdown 后分次追加。

        图片自动回填：convert 产出的图片块只是占位（token 为空），每批插入后按官方
        三步流程补齐——读取图片（http(s) 按 URL 下载；本地路径相对 ``base_dir`` 解析，
        缺省 CWD，:meth:`append_markdown_from_file` 自动传 md 文件所在目录），以图片
        块 ID 为 parent_node 调「上传图片素材」（parent_type=docx_image），再 PATCH
        ``replace_image`` 回写素材 ID（不传宽高，服务端自动探测实际尺寸）。单张图片
        失败仅记 warning 不中断整次追加（占位块保留）。

        :param document_id: 文档 token
        :param markdown: markdown 文本；为空或全空白时不发请求，返回 ``{"code": -1}`` 错误 dict
        :param base_dir: markdown 中相对路径图片的解析基准目录（str 或 Path）
        :return: 最后一次「创建嵌套块」的响应 dict（data.block_id_relations 为
            临时 id → 真实 block_id 的映射）；转换结果为空时返回 None
        https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/document-docx/docx-v1/document/convert
        """
        if not markdown or not markdown.strip():
            msg = "待插入的markdown不能为空"
            logger.error(msg)
            return {"code": -1, "msg": msg}
        convert_res = self.api.http_call(
            CORP_API_TYPE["DOC_BLOCK_CONVERT"],
            {"content_type": "markdown", "content": markdown},
        )
        blocks = convert_res["data"]["blocks"]
        # Table 块的 merge_info 为只读字段，插入前须剥离（官方要求），否则服务端报错
        for block in blocks:
            if block.get("block_type") == 31:  # 31 = Table 块
                block.get("table", {}).get("property", {}).pop("merge_info", None)
        blocks_by_id = {block["block_id"]: block for block in blocks}
        first_level_ids = convert_res["data"]["first_level_block_ids"]
        # 临时块 id → 图片源（URL 或本地路径），插入后逐张回填素材
        image_urls = {
            entry["block_id"]: entry["image_url"]
            for entry in convert_res["data"].get("block_id_to_image_urls", [])
        }

        # 按顶层子树分批：单次「创建嵌套块」上限 1000 块（descendants 与 children_id 各 1-1000）；
        # 单棵子树自身超限（如超大表格）无法再按子树切分，发出去必被服务端拒绝，
        # 在此预检报错（convert 只读无副作用，此时文档未被修改）
        trees = [
            (top_id, self._collect_subtree([top_id], blocks_by_id))
            for top_id in first_level_ids
        ]
        batches, batch, size = [], [], 0
        for top_id, tree in trees:
            if len(tree) > self._CONVERT_INSERT_LIMIT:
                msg = f"单个顶层块子树含 {len(tree)} 块，超过单次插入上限 {self._CONVERT_INSERT_LIMIT}（如超大表格），请拆分 markdown 后分次追加"
                raise ValueError(msg)
            if batch and size + len(tree) > self._CONVERT_INSERT_LIMIT:
                batches.append(batch)
                batch, size = [], 0
            batch.append((top_id, tree))
            size += len(tree)
        if batch:
            batches.append(batch)

        response = None
        shortUrl, method = CORP_API_TYPE["DOC_BLOCK_CREATE_NESTED"]
        # 文档根块的 block_id 即 document_id：对根块创建嵌套子块 = 插入到文档顶层末尾
        url = sub_url(shortUrl, DOCUMENT_ID=document_id, BLOCK_ID=document_id)
        for batch in batches:
            descendants = [block for _, tree in batch for block in tree]
            children_id = [top_id for top_id, _ in batch]
            # 多批背靠背连发，插入前先节流，避免撞单篇文档编辑限频
            self._pace_docx_edit()
            response = self.api.http_call(
                [url, method], {"children_id": children_id, "descendants": descendants}
            )
            # 本批插入的图片块：读取/下载 → 上传素材 → replace_image 回写
            relations = {
                r["temporary_block_id"]: r["block_id"]
                for r in response["data"].get("block_id_relations", [])
            }
            for temp_id, image_url in image_urls.items():
                real_id = relations.get(temp_id)
                if real_id is None:
                    continue
                try:
                    self._fill_image(document_id, real_id, image_url, base_dir)
                except Exception as e:
                    warn = f"图片回填失败（占位块保留）：{image_url}，原因：{e}"
                    logger.warning(warn)
        return response

    def _fill_image(self, document_id, block_id, image_url, base_dir):
        """回填图片块素材：读取图片 → 上传（parent_node=图片块 ID）→ replace_image。"""
        content, file_name = self._read_image(image_url, base_dir)
        # multipart 表单字段用 (None, 值) 元组与文件 part 混排（requests 惯用法）；
        # bytes 而非文件对象，token 过期重试时可安全重发
        files = {
            "parent_type": (None, "docx_image"),
            "parent_node": (None, block_id),
            "file_name": (None, file_name),
            "size": (None, str(len(content))),
            "file": (file_name, content),
        }
        upload_res = self.api.http_call(
            CORP_API_TYPE["DOC_IMAGE_UPLOAD"], {"files": files}
        )
        file_token = upload_res["data"]["file_token"]
        # 不传 width/height：首次更新（占位块 token 为空）时服务端自动探测实际尺寸
        shortUrl, method = CORP_API_TYPE["DOC_BLOCK_PATCH"]
        url = sub_url(shortUrl, DOCUMENT_ID=document_id, BLOCK_ID=block_id)
        self._pace_docx_edit()
        return self.api.http_call(
            [url, method], {"replace_image": {"token": file_token}}
        )

    def _read_image(self, image_url, base_dir):
        """取图片字节与文件名：http(s) 下载（超时 ``_IMAGE_DOWNLOAD_TIMEOUT`` 秒，文件名取
        URL 路径末段、剥离查询串并 percent 解码）；其余按本地路径读取，相对路径相对 base_dir 解析。"""
        if image_url.lower().startswith(("http://", "https://")):
            # 带浏览器风格 UA：部分图片 CDN 会拒绝 python-requests 默认 UA（403）
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) pten/fs_doc"
            }
            resp = requests.get(
                image_url,
                proxies=self.api.proxies,
                timeout=self._IMAGE_DOWNLOAD_TIMEOUT,
                headers=headers,
            )
            resp.raise_for_status()
            name = unquote(Path(urlparse(image_url).path).name) or "image.png"
            return resp.content, name
        path = Path(image_url)
        if not path.is_absolute() and base_dir:
            path = Path(base_dir) / path
        return path.read_bytes(), path.name

    def append_markdown_from_file(self, document_id, file_path, encoding="utf-8"):
        """从 markdown 文件读取内容后追加到文档末尾（等价于读文件后调
        :meth:`append_markdown`，两步流程与其一致；文件里的相对路径图片按
        md 文件所在目录解析）。

        :param document_id: 文档 token
        :param file_path: markdown 文件路径（str 或 ``Path``）
        :param encoding: 文件编码，缺省 utf-8；GBK 等旧编码文件需显式传入
        :return: 同 :meth:`append_markdown`
        """
        with open(file_path, encoding=encoding) as f:
            content = f.read()
        return self.append_markdown(
            document_id, content, base_dir=Path(file_path).resolve().parent
        )

    @staticmethod
    def _collect_subtree(top_ids, blocks_by_id):
        """BFS 收集一批顶层块及其全部子孙块（先父后子、同级按序，即文档顺序）。"""
        collected = []
        queue = deque(top_ids)
        while queue:
            block = blocks_by_id[queue.popleft()]
            collected.append(block)
            queue.extend(block.get("children", []))
        return collected

    def delete_last_blocks(self, document_id, count=1):
        """删除文档末尾 count 个顶层块（任意类型，含其全部子块）。

        取根 page 块（单页优先、拿不到再全量聚合）后按其 children 的长度定位末尾区间，对根块调「删除块」
        （区间左闭右开）：删除 ``[len-count, len)``。顶层块不足 count 时按现有数量
        全删；文档没有顶层块时不发请求返回 None。删除会连带块的子树（如整个列表）。
        注意：表格块整体可删，但其行列的增删须走更新块接口（本封装未封装）。

        :param document_id: 文档 token
        :param count: 待删除的末尾顶层块数，须 >= 1
        :return: 删除成功返回 batch_delete 响应 dict（data.document_revision_id 为
            删除后的文档版本号）；文档无顶层块时返回 None（不发请求）
        https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/batch_delete
        """
        if count < 1:
            msg = f"count 须为不小于 1 的整数，当前为 {count}"
            raise ValueError(msg)
        # 根 page 块的 block_id 即 document_id，其 children 为顶层块的有序 id 列表；
        # 根块在文档序中排第一，单页通常即含根块，免为读 children 而全量聚合，拿不到再全量聚合兜底
        res = self.list_blocks(document_id, fetch_all=False)
        root = next(
            (b for b in res["data"].get("items", []) if b["block_id"] == document_id),
            None,
        )
        if root is None:
            items = self.list_blocks(document_id)["data"].get("items", [])
            root = next((b for b in items if b["block_id"] == document_id), None)
        if root is None:
            return None
        children = root.get("children", [])
        if not children:
            return None
        # 顶层块不足 count 时按现有数量全删（start 钳到 0，不发越界区间）
        start = max(len(children) - count, 0)
        shortUrl, method = CORP_API_TYPE["DOC_BLOCK_BATCH_DELETE"]
        # 父块为文档根块（block_id = document_id），删除其 children 区间 [start, len)
        url = sub_url(shortUrl, DOCUMENT_ID=document_id, BLOCK_ID=document_id)
        self._pace_docx_edit()
        return self.api.http_call(
            [url, method], {"start_index": start, "end_index": len(children)}
        )
