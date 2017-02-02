# AWS Garbage Collector

A lib/cli tool that allows to cleanup a certain resources older than a given  
timeout in a given AWS zone. Initially developed to cleanup zone after a  
Kubernetes/KuberDock cluster.

Supported resources:
* ELB
* Auto-scaling gropus
* VMs
* Volumes
* Security gropus
* Elastic IPs
* VPCs

## Installation
```
git clone https://github.com/cloudlinux/aws-gc.git && cd aws-gc
# You may want to use venv here
python setup.py install 
``` 

## Usage
Command line:
```
aws-gc clean \
    -Z ${AWS_REGION} \
    -u ${AWS_ACCESS_KEY_ID} \
    -p ${AWS_SECRET_ACCESS_KEY} \
    -O ${AWS_CLEAN_TIMEOUT} \
    -n ${AWS_RESOURCE_NAME_PREFIX}
```
Python import:
```
from aws_gc import clean_aws
```

## Related projects:
OpenNebula Garbage Collector: https://github.com/cloudlinux/opennebula-gc
