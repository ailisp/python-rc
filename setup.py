import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="python-rc",  # Replace with your own username
    version="0.4.0",
    author="Bo Yao",
    author_email="icerove@gmail.com",
    description="Python remote control library for programmatically control remote machines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ailisp/python-rc",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Clustering",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Systems Administration"
    ],
    install_requires=[
        'retry',
        'PyYAML',
        'humanfriendly',
        'libtmux',
        'py-term',
        'pytimeparse',
    ],
    python_requires='>=3.6',
    scripts=['bin/rc']
)
