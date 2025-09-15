from setuptools import setup

setup(
    name='zarrcade',
    version='0.1.0',
    py_modules=['zarrcade'],
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'zarrcade = zarrcade.cli:cli',
        ],
    },
)