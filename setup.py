# -*- coding: utf-8 -*-

from codecs import open
from setuptools import setup, find_packages

requires = ["apscheduler", "lunardate", "openai", "pycryptodome"]
test_requirements = [
    "pytest>=3",
    "pytest-mock>=3",
]

with open("README.md", "r", "utf-8") as f:
    readme = f.read()

setup(
    name="pten",
    version="0.4.2",
    description="A tool to use WeWork(企业微信) and feishu(飞书) API quickly and easily",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="PENGyong",
    author_email="1203029076@qq.com",
    url="https://github.com/bendell02/pten",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=requires,
    tests_require=test_requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="wework qywx wechat weixin robot app",
)
