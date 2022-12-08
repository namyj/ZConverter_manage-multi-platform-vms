import re
import os
import json
import platform
import argparse
import threading

lock = threading.Lock()
parser = argparse.ArgumentParser()
PLATFORM = platform.system()

parser.add_argument('--Func', dest="Func")
parser.add_argument('--ConfigFilePath', dest="ConfigFilePath")
parser.add_argument('--PemKeyFilePath', dest="PemKeyFilePath")
parser.add_argument('--Profile', dest="Profile")
parser.add_argument('--CompartmentId', dest="CompartmentId")
parser.add_argument('--AvailabilityDomain', dest="AvailabilityDomain")
parser.add_argument('--OS', dest="OS")
parser.add_argument('--OSVersion', dest="OSVersion")
parser.add_argument('--Shape', dest="Shape")
parser.add_argument("--Name", dest="Name")
parser.add_argument('--Region', dest="Region")
parser.add_argument("--InstanceId", dest="InstanceId")

args = parser.parse_args()

Func = args.Func
ConfigFilePath = args.ConfigFilePath
PemKeyFilePath = args.PemKeyFilePath
CompartmentId = args.CompartmentId
AvailabilityDomain = args.AvailabilityDomain
OS = args.OS
OSVersion = args.OSVersion
Shape = args.Shape
Name = args.Name
Region = args.Region
InstanceId = args.InstanceId

if PLATFORM == "Windows":
    USERPATH = '/'.join(op for op in ConfigFilePath.split('\\')[:-1])
else:
    USERPATH = '/'.join(op for op in ConfigFilePath.split('/')[:-1])

# input
# ConfigFilePath, PemKeyFilePath
def getConfig():
    try:
        config = {
            'user': None,
            'fingerprint': None,
            'key_file': None,
            'tenancy': None,
            'region': None
        }
        new_file = []
        profile = None
        
        with open(ConfigFilePath, 'r') as fr:
            lines = fr.readlines()
            
            for line in lines:
                result = line.strip().rstrip('\n')
                # if (profile is None) and (re.match(r'^\[[a-zA-Z0-9]+\]',result)) and (re.sub(r"[^a-zA-Z0-9]", "", result).lower() == Profile.lower()): # Case#1: user specify profile
                if (profile is None) and (re.match(r'^\[[a-zA-Z0-9]+\]',result)): # Case#2: user do not specify profile
                    profile = re.sub(r"[^a-zA-Z0-9]", "", result)
                    new_file.append("[{}]\n".format(profile))
                
                # Get values from config file 
                elif (profile is not None) and (result != ""):
                    key, value = result.split("=")

                    if (key in list(config.keys())) and (config[key] is None):
                        if key == 'key_file':
                            value = PemKeyFilePath
                        config[key] = value 
                        new_file.append("{}={}\n".format(key,value)) 
                
                # Done 
                if (len(new_file) >= 6):
                    break
                
        if (profile is None):
            exit("CONFIG FILE ERROR : Profile is NONE")
        if (len(new_file) < 6):
            exit("CONFIG FILE ERROR : Config file value ERROR")
        
        # Write new config file
        lock.acquire()
        with open(ConfigFilePath, mode='w') as fw:
            fw.writelines(new_file)
        lock.release()

        return ConfigFilePath, profile
    except Exception as e:
        print("error: {}".format(e))

# input
# ConfigFilePath, PemKeyFilePath
def getCompartmentList(config, profile):
    """
    - print compartments list in a specified compartment (if not specified, will use the tenancy id(root compartment id) from the config file)
    - Compartment ID <- "id"
    - Compartment Name <- "name"
    [
        {
            "compartment-id": "ocid1.tenancy.oc1..aaaaaaaajogwl6jnomflxqccnilvwvp2wrv6uwbnjzhsrac2l3vwz2onycrq",
            "defined-tags": {
                "Oracle-Tags": {
                    "CreatedBy": "oracleidentitycloudservice/oracle@zconverter.com",
                    "CreatedOn": "2022-04-14T06:18:25.373Z"
                }
            },
            "description": "ZConverter",
            "freeform-tags": {
                "namespace": "ZConverter"
            },
            "id": "ocid1.compartment.oc1..aaaaaaaal3amlmpi7axdzzfiuwrplkwehvmcl3yzxbsgrg2k7vio4ijntsma",
            "inactive-status": null,
            "is-accessible": null,
            "lifecycle-state": "ACTIVE",
            "name": "ZConverter",
            "time-created": "2022-04-14T06:18:25.493000+00:00"
        },
        ...
    ]
    """
    try:
        command = "oci iam compartment list --config-file \"{}\" --profile \"{}\" --include-root".format(config, profile)
        p = os.popen(command).read()
        try:
            results = json.loads(p)
            if 'data' in results.keys(): 
                print(json.dumps(results["data"]))
        except:
            print([])

    except Exception as e:
        print('error : ',e)
        pass
      
# input
# ConfigFilePath, PemKeyFilePath, CompartmentId, AvailabilityDomain, (+ Region)
def getShapeList(config, profile):
    """
    - print shapes that can be used to launch instance within the specified compartment 
    """
    try:
        # command = "oci compute shape list --config-file \"{}\" --profile \"{}\" -c \"{}\" --region \"{}\" --availability-domain \"{}\" --all".format(config, profile, CompartmentId, Region, AvailabilityDomain)
        command = "oci compute shape list --config-file \"{}\" --profile \"{}\" -c \"{}\" --availability-domain \"{}\" --all".format(config, profile, CompartmentId, AvailabilityDomain)
        p = os.popen(command).read()
        results = json.loads(p)
        print(json.dumps(results["data"]))
        
    except Exception as e:
        print('error : ',e)

# input
# ConfigFilePath, PemKeyFilePath, CompartmentId
def getRegionSubscription(config, profile):
    """
    - print regions for the specified tenancy (if not specified, will use the tenancy of config file(root compartment))
    """
    try:
        command = "oci iam region-subscription list --config-file \"{}\" --profile \"{}\"".format(config, profile)
        p = os.popen(command).read()
        try:
            results = json.loads(p)
            
            List = []
            if 'data' in results.keys():
                for i in range(len(results["data"])):
                    _results = getAvailabilityDomainsList(config, profile, results["data"][i]["region-name"])
                    for j in range(len(_results)):
                        _results[j]["region"] = results["data"][i]["region-name"] 
                        List.append(_results[j])
                
            print(json.dumps(List))
        except:
            print([])
    except Exception as e:
        print("error : ",e)
# sub func
def getAvailabilityDomainsList(config, profile, region):
    """
    - print availability domains in your compartment
    """
    try:
        command = "oci iam availability-domain list --config-file \"{}\" --profile \"{}\" -c \"{}\" --region \"{}\"".format(config, profile, CompartmentId, region)
        p = os.popen(command).read()
        try:
            results = json.loads(p)

            if 'data' in results.keys():
                return results["data"]
            else:
                return []
        except:
            return []
    except Exception as e:
        print("error : ",e)


# input
# ConfigFilePath, PemKeyFilePath, CompartmentId
def getImageList(config, profile):
    try:
        command = "oci compute image list --config-file \"{}\" --profile \"{}\" -c \"{}\" --lifecycle-state AVAILABLE --sort-by DISPLAYNAME --sort-order ASC --all".format(config, profile, CompartmentId)
        p = os.popen(command).read()
        try:
            results = json.loads(p)
            
            if 'data' in results.keys(): 
                print(json.dumps(results["data"]))
        except:
            print([])
        
    except Exception as e:
        print('error : ',e)
        pass

# input
# ConfigFilePath, PemKeyFilePath, CompartmentId, OS, OSVersion, Shape
def matchShapeByOS(config, profile):
    try:
        command = "oci compute image list --config-file \"{}\" --profile \"{}\" -c \"{}\" --lifecycle-state AVAILABLE --operating-system \"{}\" --operating-system-version \"{}\" --shape \"{}\" --sort-by TIMECREATED --sort-order ASC --all".format(config, profile, CompartmentId, OS, OSVersion, Shape)
        p = os.popen(command).read()
        try:
            results = json.loads(p)
            
            if 'data' in results.keys():
                print(json.dumps(results["data"]))
        except:
            print([])
        
    except Exception as e:
        print('error : ',e)
        pass

# input
# ConfigFilePath, PemKeyFilePath, CompartmentId
def getVcnList(config, profile):
    """
    - print virtual cloud networks (VCNs) in the specified compartment. 
    - if VCN does not have any subnet, subnet list is empty ([]) 
    [
        {
            "compartment-id": "ocid1.tenancy.oc1..aaaaaaaajogwl6jnomflxqccnilvwvp2wrv6uwbnjzhsrac2l3vwz2onycrq",
            "display-name": "vcn-20210421-1418",
            "vcn-domain-name": "vcn04211421.oraclevcn.com",
            "vcn_id": "ocid1.vcn.oc1.ap-seoul-1.amaaaaaankn436qaj3c3baihslzlwaipfaoptllofxjq6zgwvdhnkh3sxkcq",
            "subnet": [
                {
                    "display-name": "subnet-20210421-1418",
                    "security-list-ids": [
                        "ocid1.securitylist.oc1.ap-seoul-1.aaaaaaaaovmcnnl5vpuh4d4ye247jszsaarc3lx7pjosyd7oyfml4nlpdvra"
                    ],
                    "subnet-domain-name": "subnet04211421.vcn04211421.oraclevcn.com",
                    "subnet_id": "ocid1.subnet.oc1.ap-seoul-1.aaaaaaaaikxwifqksivdvnvl27k6mffo7cnvqv4xhw4rvcgjnc7yc7ydkc2q"
                }
            ]
        },
        ...
    ]
    """
    try:
        command = "oci network vcn list --config-file \"{}\" --profile \"{}\" -c \"{}\" --lifecycle-state AVAILABLE --sort-by TIMECREATED --sort-order DESC --all ".format(config, profile, CompartmentId)
        command += "--query \"data[*].{\\\"display-name\\\":\\\"display-name\\\",\\\"vcn_id\\\":\\\"id\\\",\\\"vcn-domain-name\\\":\\\"vcn-domain-name\\\",\\\"compartment-id\\\":\\\"compartment-id\\\"}\""
        p = os.popen(command).read()
        try:
            results = json.loads(p)

            for vcn in results:
                vcn["subnet"] = getSubnetList(config, profile, vcn["vcn_id"])

            print(json.dumps(results))
        except:
            print([])
    
    except Exception as e:
        print("error: {}".format(e))
# sub func
def getSubnetList(config, profile, vcn_id):
    """
    - get available subnets in the specified VCN and the specified compartment.
    """
    try:
        command = "oci network subnet list --config-file \"{}\" --profile \"{}\" -c \"{}\" --vcn-id \"{}\" --lifecycle-state AVAILABLE --sort-by TIMECREATED --sort-order DESC --all ".format(config, profile, CompartmentId, vcn_id)
        command += "--query \"data[*].{\\\"display-name\\\":\\\"display-name\\\",\\\"subnet_id\\\":\\\"id\\\",\\\"security-list-ids\\\":\\\"security-list-ids\\\",\\\"subnet-domain-name\\\":\\\"subnet-domain-name\\\"}\""
        p = os.popen(command).read()
        try:
            results = json.loads(p)
            return results
        except:
            return []
    except Exception as e:
        print("error: {}".format(e))


# input
# ConfigFilePath, PemKeyFilePath, CompartmentId, Region, AvailabilityDomain, Name, InstanceId
def getInstanceInfo(config, profile):
    """
    - list Instances Info by Name and InstanceId (If the isntance does not exist, print [])
    - lifecycle_state : PROVISIONING -> RUNNING -> STOPPING -> STOPPED -> TERMINATING -> TERMINATED
    - case1: InstanceId is not None, Instance Info exist -> list the Instance Info which have same Instance Id
    - case2: InstanceId is not None, Instane Info does not exist -> print []
    - case3: InstanceId is None -> list all Instance Info which have same name.
    # case 1
    [
        {
            "display_name": "win16zcmtest",
            "id": "ocid1.instance.oc1.ap-seoul-1.anuwgljrnkn436qcwmkjvjaemqa6ee4amc6beugvxiviak3ee44f4g6jbe7q",
            "lifecycle_state": "RUNNING",
            "region": "ap-seoul-1",
            "publicip": "132.226.232.32"
        }
    ]
    # case 2
    []
    # case 3
    [
        {...},{...},{...}
    ]

    """
    try:
        final_result = []
        command = "oci compute instance list --config-file \"{}\" --profile \"{}\" -c \"{}\" --region \"{}\" --availability-domain \"{}\" --display-name \"{}\" --sort-by TIMECREATED --sort-order ASC --all ".format(config, profile, CompartmentId, Region, AvailabilityDomain, Name)
        command += "--query \"data[*].{\\\"id\\\":\\\"id\\\",\\\"display_name\\\":\\\"display-name\\\",\\\"lifecycle_state\\\":\\\"lifecycle-state\\\",\\\"region\\\":\\\"region\\\"}\""
        p = os.popen(command).read()

        try:
            result = json.loads(p)

            for i in result:
                # Get public IP
                command = "oci compute instance list-vnics --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" ".format(config, profile, i["id"])
                command += "--query \"data[*].\\\"public-ip\\\"\" 2>&1"
                p = os.popen(command).read()
                search_result = re.search(r'\[(.*\s)*\]', p)

                if search_result:
                    ips = json.loads(search_result.group(0))
                    i["publicip"] = ','.join(op for op in ips)

                if (InstanceId) and (i["id"] == InstanceId):
                    final_result.append(i)
                    break
            
            if InstanceId:
                print(json.dumps(final_result))
            else:
                print(json.dumps(result))
        except:
            print([])
    except Exception as e:
        print("error: {}".format(e))

# input
# ConfigFilePath, PemKeyFilePath, InstanceId
# def getInstanceInfoByIid(config, profile):
#     """
#     - list Instances Info by InstanceId (If the isntance does not exist, print [])
#     - lifecycle_state : PROVISIONING -> RUNNING -> STOPPING -> STOPPED -> TERMINATING -> TERMINATED
#     [
#         {
#             "display_name": "win16zcmtest",
#             "id": "ocid1.instance.oc1.ap-seoul-1.anuwgljrnkn436qcwmkjvjaemqa6ee4amc6beugvxiviak3ee44f4g6jbe7q",
#             "lifecycle_state": "RUNNING",
#             "region": "ap-seoul-1",
#             "publicip": "132.226.232.32"
#         }
#     ]
#     """
#     try:
#         if InstanceId:
#             command = "oci compute instance get --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" ".format(config, profile, InstanceId)
#             command += "--query \"data.{\\\"id\\\":\\\"id\\\",\\\"display_name\\\":\\\"display-name\\\",\\\"lifecycle_state\\\":\\\"lifecycle-state\\\",\\\"region\\\":\\\"region\\\"}\""
#             p = os.popen(command).read()
#             try:
#                 result = json.loads(p)
                
#                 # get Public Ip
#                 command = "oci compute instance list-vnics --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" ".format(config, profile, result["id"])
#                 command += "--query \"data[*].\\\"public-ip\\\"\" 2>&1"
#                 p = os.popen(command).read()
#                 search_result = re.search(r'\[(.*\s)*\]', p)
#                 if search_result:
#                     ips = json.loads(search_result.group(0))
#                     result["publicip"] = ','.join(op for op in ips)
                
#                 print(json.dumps(result))
#             except:
#                 print([])
#         else:
#             print([])
            
#     except Exception as e:
#         print("error: {}".format(e))


# input
# ConfigFilePath, PemKeyFilePath, CompartmentId, AvailabilityDomain
def getInstanceList(config, profile):
    """
    - list Instance info by CompartmentId and AvailabilityDomain (If there is no instance, print [])
    - lifecycle_state : PROVISIONING -> RUNNING -> STOPPING -> STOPPED -> TERMINATING -> TERMINATED
    [
        {
            "display_name": "Korea-Pub-ZCM",
            "id": "ocid1.instance.oc1.ap-seoul-1.anuwgljrnkn436qclur6bhvengfx5q5s5k7ob5ctjv4twmbaobvsrxn7jgqq",
            "lifecycle_state": "STOPPED",
            "region": "ap-seoul-1",
            "publicip": "146.56.132.183"
        },
        ...
    ]
    """
    try:
        command = "oci compute instance list --config-file \"{}\" --profile \"{}\" -c \"{}\" --availability-domain \"{}\" --sort-by DISPLAYNAME --sort-order ASC --all ".format(config, profile, CompartmentId, AvailabilityDomain)
        command += "--query \"data[*].{\\\"id\\\":\\\"id\\\",\\\"display_name\\\":\\\"display-name\\\",\\\"lifecycle_state\\\":\\\"lifecycle-state\\\",\\\"region\\\":\\\"region\\\"}\""
        p = os.popen(command).read()

        try:
            result = json.loads(p)

            for i in result:
                command = "oci compute instance list-vnics --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" ".format(config, profile, i["id"])
                command += "--query \"data[*].\\\"public-ip\\\"\" 2>&1"
                p = os.popen(command).read()
                search_result = re.search(r'\[(.*\s)*\]', p)

                if search_result:
                    ips = json.loads(search_result.group(0))
                    i["publicip"] = ','.join(op for op in ips)
            
            print(json.dumps(result))

        except:
            print([])
            
    except Exception as e:
        print("error: {}".format(e))


if __name__ == "__main__":
    os.environ["OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING"] = "True"
    # if (ConfigFilePath == None) or (PemKeyFilePath == None) or (Profile == None): # Case#1: user specify profile
    if (ConfigFilePath == None) or (PemKeyFilePath == None): # Case#2: user do not specify profile
        exit("ConfigFilePath or PemKeyFilePath None ERROR")
    
    config, profile = getConfig()
        
    if (Func == "Compartment"):
        getCompartmentList(config,profile)

    if (Func == "Subnet"):
        getVcnList(config,profile)

    if (Func == "Shape"):
        getShapeList(config, profile)
    
    if (Func == "Region"):
        getRegionSubscription(config, profile)
    
    if (Func == "Image"):
        getImageList(config, profile)
        
    if (Func == "matchShapeByOS"):
        matchShapeByOS(config, profile)
        
    if (Func == "Instance"):
        # getInstanceInfoByIid(config, profile)
        getInstanceInfo(config, profile)

    if (Func == "AllInstance"):
        getInstanceList(config, profile)
