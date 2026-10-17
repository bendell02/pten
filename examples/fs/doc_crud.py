"""飞书文档（docx）示例。

运行前提：[fs] 配置 app_id、app_secret，且应用具备 docx:document 权限；
append_markdown 的 convert 环节另需 docx:document.block:convert，带图片时
素材上传另需 docs:document.media:upload 等任一上传权限。
注意：本例会真实创建一篇文档并追加内容；结束时删除本例追加的部分块，
文档本身保留（可在飞书云空间手动删除）。
运行方式：python examples/fs/doc_crud.py
"""

from pten.fs_doc import FsDoc

if __name__ == "__main__":
    doc = FsDoc()

    # 1. 创建文档（url 可拼为 https://<域名>/docx/<document_id>）
    create_res = doc.create_document(title="pten示例文档")
    document_id = create_res["data"]["document"]["document_id"]
    print(f"document_id: {document_id}")

    # 2. 追加一段纯文本到文档末尾（多行文本进同一个文本块，\n 为软换行）
    print(doc.append_text(document_id, "第一行\n第二行"))

    # 3. markdown 转换后追加到末尾（标题/列表/表格转成对应的块结构；
    #    超过 1000 块会自动按顶层子树分批插入）
    print(doc.append_markdown(document_id, "# 小节\n\n- 项目一\n- 项目二\n"))

    # 3b. 也可以从 markdown 文件读取后追加（图片会自动下载/读取并上传回填到图片块，
    #     相对路径图片按 md 文件所在目录解析；GBK 旧文件显式传 encoding="gbk"）：
    # print(doc.append_markdown_from_file(document_id, "report.md"))

    # 4. 获取文档纯文本内容（data.content，段落以 \n 分隔）
    print(doc.get_raw_content(document_id))

    # 5. 获取全部块（默认自动翻页聚合，data.items 为全量块；
    #    根 page 块的 children 即顶层块顺序）
    print(doc.list_blocks(document_id))

    # 6. 删除末尾 3 个顶层块（任意类型：文本/标题/列表都行，连带子树）
    print(doc.delete_last_blocks(document_id, count=3))

    # 7. 文档基本信息（revision_id 随编辑递增）
    print(doc.get_document(document_id))
