# Initial author: Dmitry Tyzhnenko <t.dmitry@gmail.com>

import time
from datetime import datetime, timedelta, tzinfo

import netaddr
import boto3.ec2


JENKINS_USER = 'jenkins-ci'


class UTC(tzinfo):

    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)


def wait_for(func, tries=50, interval=10, fail_silently=False):
    """
    Waits for function func to evaluate to True.

    :param func:            Function that should evaluate to true.
    :param tries:           Number of tries to make.
    :param interval:        Interval in second between consequent tries.
    :param fail_silently:   If False then asserts that func evaluated to True.
    """
    for _ in xrange(tries):
        func_value = func()
        if func_value:
            break
        time.sleep(interval)
    if not fail_silently:
        assert func_value


def _clean_aws_elbs(aws_zone, user_key, user_secret_key, vpcs_to_delete):
    elb = boto3.client(
        'elb',
        aws_zone,
        aws_access_key_id=user_key,
        aws_secret_access_key=user_secret_key)

    print("--- Remove Elastic Load Balancers ---")
    # Clean Elastic Load Balancers
    for vpc in vpcs_to_delete:
        balancers = elb.describe_load_balancers()['LoadBalancerDescriptions']
        balancers = [b for b in balancers if b['VPCId'] == vpc.id]
        for b in balancers:
            text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
                uid="elb-********",
                name="{}({})".format(b['LoadBalancerName'][:8], vpc.id),
                started=b['CreatedTime'].ctime())
            print(text)
            elb.delete_load_balancer(
                LoadBalancerName=b['LoadBalancerName']
            )


def _clean_aws_asg(aws_zone, user_key, user_secret_key, name_prefix):
    autoscale = boto3.client(
        'autoscaling',
        aws_zone,
        aws_access_key_id=user_key,
        aws_secret_access_key=user_secret_key)

    #  Delete AutoScale groups
    print("--- Remove AutoScale groups ---")
    for group in autoscale.describe_auto_scaling_groups()['AutoScalingGroups']:
        if next((tag for tag in group['Tags'] if 'KubernetesCluster'
                in tag.get('Key') and name_prefix in tag.get('Value')), None):
            group_name = group['AutoScalingGroupName']
            text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
                uid="asg-********",
                name=group_name,
                started=group['CreatedTime'].ctime())
            print(text)
            autoscale.delete_auto_scaling_group(
                AutoScalingGroupName=group_name)


def _clean_aws_volumes(volumes_to_delete):
    print("--- Remove Elastic Block Storages (Volumes) ---")
    for vol in volumes_to_delete:
        # Delete EBS
        vol_name = next((tag.get('Value') for tag in vol.tags
                         if tag.get('Key') == 'Name'))
        text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
            uid=vol.id,
            name=vol_name,
            started="N/A")
        print(text)
        vol.delete()


def _clean_aws_sgroups(sgroups_to_delete):
    # Delete Secutiry Groups
    print("--- Cleanup Secutiry Groups ---")
    for sgroup in sgroups_to_delete:
        if sgroup.group_name == 'default':
            continue

        text = "{uid:<15} {name:25} {started!s:10} - cleaned up".format(
            uid=sgroup.group_id,
            name=sgroup.group_name,
            started="N/A")
        print(text)

        linked_groups = next(
            (p for p in sgroup.meta.data['IpPermissions']
             if p['UserIdGroupPairs']), {})
        linked_groups = linked_groups.get('UserIdGroupPairs', [])
        if linked_groups:
            sgroup.revoke_ingress(
                IpPermissions=[
                    {
                        'IpProtocol': '-1',
                        'UserIdGroupPairs': linked_groups}])

    print("--- Remove Secutiry Groups ---")
    for sgroup in sgroups_to_delete:
        if sgroup.group_name == 'default':
            continue

        text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
            uid=sgroup.group_id,
            name=sgroup.group_name,
            started="N/A")
        print(text)
        sgroup.delete()


def _clean_aws_vms(vms_to_delete):
    print("--- Remove Instances ---")
    for vm in vms_to_delete:
        # Delete VM
        vm_name = next((tag.get('Value') for tag in vm.tags
                       if tag.get('Key') == 'Name'))
        text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
            uid=vm.id,
            name=vm_name,
            started=vm.launch_time.ctime())
        print(text)
        vm.terminate()

        def check_state():
            vm.reload()
            return vm.state['Name'] == 'terminated'
        wait_for(check_state)


def _clean_aws_vpcs(name_prefix, vpcs_to_delete):
    print("--- Remove VPCs ---")
    # Delete VPCs
    for vpc in vpcs_to_delete:
        vpc.reload()
        subnets = list(vpc.subnets.all())
        igws = list(vpc.internet_gateways.all())
        routes = list(vpc.route_tables.filter(Filters=[
            {
                'Name': 'tag:KubernetesCluster',
                'Values': [
                    '{}*'.format(name_prefix),
                ]
            }]).all())
        dhcpopt = vpc.dhcp_options
        for s in subnets:
            s.delete()
        for gw in igws:
            gw.detach_from_vpc(VpcId=vpc.vpc_id)
            gw.delete()
        for r in routes:
            net_172 = netaddr.IPNetwork('172.16.0.0/12')
            for rr in r.routes:
                if netaddr.IPNetwork(rr.destination_cidr_block) in net_172:
                    # Skip routes to local private net
                    continue
                rr.delete()
            r.delete()

        vpc_name = next((tag.get('Value') for tag in vpc.meta.data['Tags']
                         if tag.get('Key') == 'Name'))
        text = "{uid:<15} {name:25} {started!s:10} - deleted".format(
            uid=vpc.id,
            name=vpc_name,
            started="N/A")
        print(text)
        vpc.delete()
        dhcpopt.delete()


def _clean_aws_eips(aws_zone, user_key, user_secret_key, ips_to_delete):
    ec2 = boto3.client(
        'ec2',
        aws_zone,
        aws_access_key_id=user_key,
        aws_secret_access_key=user_secret_key)
    print("--- Remove Elastic IPs ---")
    # Delete Elastic IPs
    for ip in ips_to_delete:
        eip = next((a for a in ec2.describe_addresses()['Addresses']
                    if a.get('PublicIp') == ip), None)
        if not eip:
            # Wnen public is not an elastic ip
            continue
        text = "{uid:<15} {name:25} {started!s:10} - released".format(
            uid=eip['AllocationId'],
            name=eip['PublicIp'],
            started="N/A")
        print(text)
        ec2.release_address(AllocationId=eip['AllocationId'])


def clean_aws(aws_zone, user_key, user_secret_key, hours, name_prefix):
    now = datetime.now(UTC())
    delta = timedelta(hours=int(hours))
    ec2 = boto3.resource(
        'ec2',
        aws_zone,
        aws_access_key_id=user_key,
        aws_secret_access_key=user_secret_key)

    vms = ec2.instances.filter(Filters=[
        {
            'Name': 'tag:KubernetesCluster',
            'Values': [
                '{}*'.format(name_prefix),
            ]
        },
        {
            "Name": 'instance-state-name',
            "Values": ["running"]}]).all()
    vpcs_to_delete = set()
    volumes_to_delete = set()
    sgroups_to_delete = set()
    ips_to_delete = []
    vms_to_delete = []
    print("{uid:<15} {name:25} {started}".format(
        uid="#", name="Resource Name", started="Started"))

    for vm in vms:
        vm_name = next((tag.get('Value') for tag in vm.tags
                       if tag.get('Key') == 'Name'))
        text = "{uid:<15} {name:25} {started!s:10}".format(
            uid=vm.id,
            name=vm_name,
            started=vm.launch_time.ctime())
        print(text)
        if now - vm.launch_time > delta:
            vms_to_delete.append(vm)
            if vm.vpc:
                vpcs_to_delete.update([vm.vpc_id])
            if vm.public_ip_address:
                ips_to_delete.append(vm.public_ip_address)
            volumes = list(
                vm.volumes.filter(
                    Filters=[{"Name": "attachment.delete-on-termination",
                              "Values": ["false"]}]).all())
            volumes_to_delete.update(set([v.id for v in volumes]))

            sgroups_ids = [s['GroupId'] for s in vm.security_groups]
            sgroups_to_delete.update(sgroups_ids)

    vpcs_to_delete = [ec2.Vpc(v) for v in vpcs_to_delete]
    volumes_to_delete = [ec2.Volume(v) for v in volumes_to_delete]
    for sg in [ec2.SecurityGroup(s) for s in sgroups_to_delete]:
        sg.reload()
        linked_groups = next(
                (p for p in sg.meta.data['IpPermissions']
                 if p['UserIdGroupPairs']), {})
        linked_groups_ids = [
            g['GroupId'] for g in linked_groups['UserIdGroupPairs']]
        sgroups_to_delete.update(linked_groups_ids)
    sgroups_to_delete = [ec2.SecurityGroup(s) for s in sgroups_to_delete]

    _clean_aws_elbs(aws_zone, user_key, user_secret_key, vpcs_to_delete)
    _clean_aws_asg(aws_zone, user_key, user_secret_key, name_prefix)
    _clean_aws_vms(vms_to_delete)
    _clean_aws_volumes(volumes_to_delete)
    _clean_aws_sgroups(sgroups_to_delete)
    _clean_aws_eips(aws_zone, user_key, user_secret_key, ips_to_delete)
    _clean_aws_vpcs(name_prefix, vpcs_to_delete)
