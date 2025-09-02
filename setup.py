import os
from setuptools import setup

with open(os.path.join("docs", "README.md"), encoding="utf-8") as fh:
    long_desc = fh.read()

setup(
    name="x_make_pypi_x",
    version="3.0.15",
    author="Roy GM",
    author_email="eye4357@outlook.com",
    description="Makes PyPI packages.",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url="https://pypi.org/project/x_make_pypi_x/",
    packages=["x_make_pypi_x"],
    include_package_data=True,
    package_data={"x_make_pypi_x": ["*", "**/*"]},
    install_requires=['markdown', 'pdfkit'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    zip_safe=False,
)
