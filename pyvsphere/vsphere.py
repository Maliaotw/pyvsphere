import logging
from .vcenter import VcenterConfig
from .vmware_guest_facts import vmware_guest_facts
from .vmware_host_facts import vmware_host_facts
from .vmware_datastore_facts import vmware_datastore_facts
from .vmware_guest_disk_info import vmware_guest_disk_info
from .vmware_resource_pool_facts import vmware_resource_pool_facts
from .vmware_portgroup_facts import vmware_portgroup_facts
from .vmware_vm_facts import vmware_vm_facts
from .vmware_vswitch_facts import vmware_vswitch_facts
from typing import List
import concurrent.futures

logger = logging.getLogger(__name__)


class VMWARE:

    def __init__(self, VcenterConfig):
        self.VcenterConfig = VcenterConfig

    def vmware_vswitch_facts(self, esxi_hostname):
        return vmware_vswitch_facts(self.VcenterConfig, esxi_hostname)

    def vmware_guest_facts(self, show_attribute=False, datacenter='Datacenter', uuid='', schema='summary', name=''):
        return vmware_guest_facts(self.VcenterConfig, show_attribute, datacenter, uuid, schema, name)

    def vmware_datastore_facts(self, name):
        return vmware_datastore_facts(self.VcenterConfig, name)

    def vmware_vm_facts(self, *args, **kwargs):
        return vmware_vm_facts(self.VcenterConfig, *args, **kwargs)

    def vmware_portgroup_facts(self, esxi_hostname):
        return vmware_portgroup_facts(self.VcenterConfig, esxi_hostname)

    def vmware_resource_pool_facts(self):
        return vmware_resource_pool_facts(self.VcenterConfig)

    def vmware_host_facts(self, esxi_hostname):
        return vmware_host_facts(self.VcenterConfig, esxi_hostname)

    def vmware_guest_disk_info(self, moid):
        return vmware_guest_disk_info(self.VcenterConfig, moid)


class Vsphere:

    def __init__(self, VcenterConfig: VcenterConfig):
        self.vmware = VMWARE(VcenterConfig)
        self._datastores = {}
        self._vm = {}
        self._host = {}
        self._network = {}
        self._cluster = {}
        self.exclude_vm = {}
        # self.get()
        # self.clean()


    @property
    def cluster(self):
        if not self._cluster:
            return {}
        else:
            return self._cluster

    @property
    def network(self):
        if not self._network:
            return {}
        else:
            return self._network

    def get_datastores(self, name=None) -> dict:
        for datastore in self.vmware.vmware_datastore_facts(name):
            key = datastore['name']
            value = datastore
            self._datastores[key] = value
            logger.info(f"{key} {value}")

        return self._datastores

    @property
    def datastores(self):
        if not self._datastores:
            return self.get_datastores()
        else:
            return self._datastores

    def get_host_detail(self, resource):
        resource.update(self.vmware.vmware_host_facts(esxi_hostname=resource['owner']))
        for datastore in resource['ansible_datastore']:
            datastore.update(self.vmware.vmware_datastore_facts(name=datastore['name']))

        resource.update({'network': self.vmware.vmware_portgroup_facts(esxi_hostname=resource['owner'])[resource['owner']]})

        return resource

    def get_hosts(self):
        resource_objs = []

        for resource in self.vmware.vmware_resource_pool_facts():
            # key = resource['owner']
            if resource['runtime_memory_reservation_used'] != 0:
                resource_objs.append(resource)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.get_host_detail, resource) for resource in resource_objs]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    self._host[result['owner']] = result
                except Exception as exc:
                    print('get_hosts generated an exception: %s' % (exc))
                    logger.error('get_hosts generated an exception: %s' % (exc))

        return self._host

    @property
    def hosts(self):
        if not self._host:
            return self.get_hosts()
        else:
            return self._host

    def get_vm(self):
        vm_objs = []

        for vm in self.vmware.vmware_vm_facts():
            if not vm['uuid']:
                continue
            else:
                vm_objs.append(vm)
                # try:
                #     self._vm[vm['guest_name']] = self.get_vm_datatil(vm)
                # except Exception as e:
                #     logger.error(f"{vm['guest_name']} ERROR {e}")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.get_vm_datatil, vm) for vm in vm_objs]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    self._vm[result['hw_name']] = result
                except Exception as exc:
                    print('vm_objs generated an exception: %s' % (exc))
                    # logger.error(f"{vm['guest_name']} ERROR {e}")


        return self._vm

    def get_vm_datatil(self, vm):
        data = self.vmware.vmware_guest_facts(uuid=vm['uuid'])
        capacity_in_kb = sum([v['capacity_in_kb'] for v in self.vmware.vmware_guest_disk_info(moid=data['moid']).values()])
        capacity = capacity_in_kb / 1024 / 1024
        data.update({'capacity': capacity})
        logging.info(data)
        return data

    @property
    def vms(self):
        if not self._vm:
            return self.get_vm()
        else:
            return self._vm

    def get(self):
        self.get_datastores()
        self.get_hosts()
        self.get_vm()

    def clean_host(self, hostname):
        data = self._host[hostname]

        # models.NetWork 跟著集群


        data['cluster'] = data['cluster'] if data['cluster'] else data['ansible_hostname']
        self._cluster[data['cluster']] = {'name': data['cluster'], 'network': data['network']}


        for network in data['network']:
            network.update(
                {
                    'network': network['portgroup'],
                    'status': True,
                    'dhcp': True
                })
            self._network[network['network']] = network
            # data['network'].append(network['network'])
            logger.info(f"network {network['network']} {network}")


        datastore_objs = []
        for datastore in data['ansible_datastore']:
            datastore_obj = self._datastores[datastore['name']]
            datastore_objs.append(datastore_obj)

        # models.Host
        data['name'] = data['ansible_hostname']
        data['ansible_all_ipv4_addresses'] = data['ansible_all_ipv4_addresses'][0] if data[
            'ansible_all_ipv4_addresses'] else '127.0.0.1'
        # data['overall_status'] = ''

        self._host[hostname].update(data)
        return data

    def clean_vm(self, name):
        data = self._vm[name]
        hostname = data['hw_esxi_host']
        host = self.hosts[hostname]

        datastore = data['hw_datastores'][0] if data['hw_datastores'][0] else ''
        datastore = self._datastores[datastore]

        summarys = [v['summary'] for k, v in data.items() if 'eth' in k]
        network = [i for i in summarys if self._network.get(i)][0] if [i for i in summarys if self._network.get(i)] else None

        mac_address = [x['macaddress'] for x in [v for k, v in data.items() if 'eth0' in k] if x['ipaddresses']]
        mac_address = mac_address[0] if mac_address else ''
        ip_address = [x['ipaddresses'][0] for x in [v for k, v in data.items() if 'eth0' in k] if x['ipaddresses']]
        ip_address = ip_address[0] if ip_address else ''

        data.update({
            'host': host,
            'cluster': host['cluster'],
            # 'ip_address': data.get('ipv4', ''),
            'ip_address': ip_address,
            'mac_address': mac_address,
            'capacity': int(data['capacity']),
            'instance_uuid': data['instance_uuid'],
            'datastore': datastore,
            'network': network,
            'hw_guest_full_name': data['hw_guest_full_name'] if data['hw_guest_full_name'] else '',

        })

        if data['hw_power_status'] == 'poweredOff':
            # 實例已停止 不更新IP
            logger.info("實例已停止 不更新IP")

        self._vm[name].update(data)
        return data

    def clean_host_list(self):
        for name in self.hosts.keys():
            self.clean_host(name)

    def clean_vm_list(self):
        self.include_vm = {k: v for k, v in self.vms.items() if v['hw_guest_id']}
        self.exclude_vm = {k: v for k, v in self.vms.items() if not v['hw_guest_id']}

        for name in self.include_vm.keys():
            self.clean_vm(name)

    def clean(self):
        self.clean_host_list()
        self.clean_vm_list()





if __name__ == '__main__':
    vcenterconfig = VcenterConfig(hostname='192.168.10.1', username='abc', password='123456')
    vsphere = Vsphere(vcenterconfig)
