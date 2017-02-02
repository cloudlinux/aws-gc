from setuptools import setup

with open('./requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='aws-gc',
    version='0.1',
    description='AWS Garbage Collector',
    license='MIT',
    packages=['aws_gc'],
    install_requires=requirements,
    classifiers=[
        'Programming Language :: Python :: 2.7',
    ],
    entry_points={
        'console_scripts': [
            'aws-gc = aws_gc.cli:main',
        ],
    }
)
