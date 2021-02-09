
# Vsphere SDK package


## Install

```
pip install pyvsphere
```

## Use

init
```
from pyvsphere import Vsphere, VcenterConfig
vcenterconfig = VcenterConfig(hostname=settings.VCENTER_SERVER, username=settings.VCENTER_USER, password=settings.VCENTER_PASS)
vsphere = Vsphere(vcenterconfig)
vsphere.get()
vsphere.clean()
```

get clusters info
```
vsphere.cluster
```

get networks info
```
vsphere.network
```

get datastores info
```
vsphere.datastores
```

get hosts info
```
vsphere.hosts
```

get vms info
```
vsphere.vms
```


