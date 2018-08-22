"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from os import path
# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='dokuwiki-fuse',
    version='0.0.1',
    description='Fuse for Dokuwiki',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kindy/fuse-dokuwiki',

    author='Kindy Lin',

    classifiers=[
        'Development Status :: 3 - Alpha',

        # Pick your license as you wish
        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
    ],

    #   py_modules=["my_module"],
    #
    packages=['dokuwiki_fuse'],

    # For an analysis of "install_requires" vs pip's requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'dokuwiki',
        'fusepy',
        'lru_cache',
    ],

    entry_points={  # Optional
        'console_scripts': [
            'dokuwiki-fuse=dokuwiki_fuse:main',
        ],
    },
)