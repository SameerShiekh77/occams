import os
import re
from setuptools import setup, find_packages
import sys


def yield_packages(path):
    """Simple parser for requirements.txt files"""
    with open(path) as requirements:
        for line in requirements:
            if re.match('^[a-zA-Z]', line):
                yield line.strip()


HERE = os.path.abspath(os.path.dirname(__file__))
REQUIRES = list(yield_packages(os.path.join(HERE, 'requirements.txt')))
DEVELOP = list(yield_packages(os.path.join(HERE, 'requirements-develop.txt')))
README = open(os.path.join(HERE, 'README.rst')).read()

setup(
    name='occams',
    version='4.0.0-dev1',
    description='OCCAMS Application Platform',
    long_description=README,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author='RazorLabs',
    author_email='younglabs@ucsd.edu',
    url='https://github.com/razorlabs/occams',
    license='BSD',
    keywords='web wsgi bfg pylons pyramid',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIRES,
    extras_require={'develop': DEVELOP},
    tests_require=DEVELOP,
    entry_points="""\
    [paste.app_factory]
    main = occams:main
    [console_scripts]
    occams_buildassets = occams.scripts.buildassets:main
    occams_initdb = occams.scripts.initdb:main
    """,
)
