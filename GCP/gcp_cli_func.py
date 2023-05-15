import os
import re
import json
import argparse
import subprocess

parser = argparse.ArgumentParser()

parser.add_argument('--Func', dest="Func")
parser.add_argument("--CredentialsFilePath", dest="CredentialsFilePath")
parser.add_argument("--Zone", dest="Zone")
parser.add_argument("--Name", dest="Name")

args = parser.parse_args()

Func = args.Func
CredentialsFilePath = args.CredentialsFilePath
Zone = args.Zone
Name = args.Name

# input
# CredentialsFilePath
def getLogin():
    """
    - CredentialsFilePath : full path
    """
    try:
        if not os.path.isfile(CredentialsFilePath):
            exit("File ERROR: [{}] does not exist".format(CredentialsFilePath))
        
        with open(CredentialsFilePath, "r") as f:
            credentials = json.load(f)
            
        account = credentials["client_email"]
        project_id = credentials["project_id"]
        command = "gcloud auth activate-service-account \"{}\" --key-file=\"{}\" --project=\"{}\"".format(account, CredentialsFilePath, project_id)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            exit(stderr)
        else:
            return account, project_id
        
    except Exception as e:
        print("error: ",e)
# input
# CredentialsFilePath
def getZoneList(account, project_id):
    """
    -  print list of zone names by project_id
    [
        {
            "name": "us-east1-b"
        },
        ....
    ]
    """
    try:
        command = "gcloud compute zones list --account=\"{}\" --project=\"{}\" --sort-by=name --format=\"json(name)\"".format(account, project_id)
        result = os.popen(command).read()
        print(result)
    except Exception as e:
        print("error: ",e)

# input
# CredentialsFilePath, Zone
def getMachineTypeList(account, project_id):
    """
    - print Machine Type List in the specified Zone
    - to create instance
        - "name"
    [
        {
            "creationTimestamp": "1969-12-31T16:00:00.000-08:00",
            "description": "Accelerator Optimized: 1 NVIDIA Tesla A100 GPU, 12 vCPUs, 85GB RAM",
            "guestCpus": 12,
            "id": "1000012",
            "imageSpaceGb": 0,
            "isSharedCpu": false,
            "kind": "compute#machineType",
            "maximumPersistentDisks": 128,
            "maximumPersistentDisksSizeGb": "263168",
            "memoryMb": 87040,
            "name": "a2-highgpu-1g",
            "selfLink": "https://www.googleapis.com/compute/v1/projects/nm-project-356101/zones/asia-northeast1-a/machineTypes/a2-highgpu-1g",
            "zone": "asia-northeast1-a"
        },
        ....
    ]
    """
    try:
        command = "gcloud compute machine-types list --account=\"{}\" --project=\"{}\"  --zones=\"{}\" --sort-by=\"name\" --format=\"json\"".format(account, project_id, Zone)
        result = os.popen(command).read()
        
        print(result)
    except Exception as e:
        print("error: ",e)
        
# input
# CredentialsFilePath
def getImageList(account, project_id):
    """
    - print image list (and family) only public image
    - to create instance, have to specify image family & image project
        - iamge family <- "family"
        - image project <- "image_project" (parsing form selfLink)
    [
        {
            "family": "centos-7",
            "name": "centos-7-v20221004",
            "selfLink": "https://www.googleapis.com/compute/v1/projects/centos-cloud/global/images/centos-7-v20221004",
            "iamge_project": "centos-cloud"
        },
        ... 
    ]
    """
    try:
        command = "gcloud compute images list --account=\"{}\" --project=\"{}\"  --filter=\"family ~ '[a-zA-Z].*'\" --format=\"json(name,family,selfLink)\"".format(account, project_id)
        result = json.loads(os.popen(command).read())
        
        for i in result:
            tmp = re.sub("https://www.googleapis.com/compute/v1/projects/","",i["selfLink"]) 
            i["iamge_project"] = tmp.split('/')[0]

        print(json.dumps(result))
    except Exception as e:
        print("error: ",e)

# input
# CredentialsFilePath
def getFirewallRuleList(account, project_id):
    """
    - print Firewall Rules List
    - If firewall doesn't have targetTags, it apply for all instances. 
    - to create instance
        - "targetTags"
    [
        {
            "allowed": [
            {
                "IPProtocol": "tcp",
                "ports": [
                "111"
                ]
            },
            {
                "IPProtocol": "udp",
                "ports": [
                "9051-9054"
                ]
            }
            ],
            "creationTimestamp": "2022-09-05T06:15:02.355-07:00",
            "description": "zcon demo rule - nam yj",
            "direction": "INGRESS",
            "disabled": false,
            "id": "2944924207487142073",
            "kind": "compute#firewall",
            "logConfig": {
            "enable": false
            },
            "name": "zcon-demo-rule",
            "network": "***************************************************************",
            "priority": 1000,
            "selfLink": "***************************************************************",
            "sourceRanges": [
            "0.0.0.0/0"
            ],
            "targetTags": [
            "demo"
            ]
        },
        ...
    ]
    """
    try:
        # command = "gcloud compute firewall-rules list --account=\"{}\" --project=\"{}\" --format=\"json(name,sourceRanges,targetTags)\"".format(account, project_id)
        command = "gcloud compute firewall-rules list --account=\"{}\" --project=\"{}\" --format=\"json\"".format(account, project_id)
        p = os.popen(command).read()
        print(p)
    except Exception as e:
        print("error: ",e)


# input
# CredentialsFilePath, Zone
def getInstanceList(account, project_id):
    """
    - list Instances Info by Zone (If there is no Instance, print [])
    - status : PROVISIONING -> STAGING -> RUNNING -> STOPPING -> TERMINATED  -> STOPPING -> []
    [
        {
            "name": "instance-yj",
            "status": "RUNNING",
            "zone": "asia-east1-b",
            "publicip": "***.***.***.***"
        },
        ...
    ]
    """
    try:
        command = "gcloud compute instances list --account=\"{}\" --project=\"{}\"  --zones=\"{}\" --sort-by=\"name\" --format=\"json(name,status,zone.basename(),networkInterfaces[].accessConfigs[0].natIP:label=EXTERNAL_IP)\" 2>&1".format(account, project_id, Zone)
        p = os.popen(command).read()
        
        if "ERROR" in p:
            print([])
        else:
            result = json.loads(p[p.find("["):])
            for i in result:
                try:
                    i["publicip"] = i["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
                except:
                    i["publicip"] = ""
                
                if "networkInterfaces" in i.keys():
                    del(i["networkInterfaces"])
                
            print(json.dumps(result))

    except Exception as e:
        print("error: {}".format(e))

# input
# CredentialsFilePath, Zone, Name
def getInstanceInfo(account, project_id):
    """
    - print Instance Info by Name and Zone (If the Instance does not exist, print {})
    - status : PROVISIONING -> STAGING -> RUNNING -> STOPPING -> TERMINATED  -> STOPPING -> {}
    - STOPPING -> TERMINATED : When you stop the instance
    - STOPPING -> {} : When you delete the instance 
    {
        "name": "yj-test",
        "status": "RUNNING",
        "zone": "asia-east1-b",
        "publicip": "***.***.***.***"
    }
    """
    try:
        # get Instance Info
        command = "gcloud compute instances describe --account=\"{ACCOUNT}\" --project=\"{PROJECT}\" --zone=\"{ZONE}\" {NAME}  --format=\"json(name,status,zone.basename(),networkInterfaces[].accessConfigs[].natIP:label=EXTERNAL_IP)\" 2>&1".format(ACCOUNT=account, PROJECT=project_id, ZONE=Zone, NAME=Name)
        p = os.popen(command).read()

        if "ERROR" in p:
            print("{}")
        else:
            result = json.loads(p)

            try:
                result["publicip"] = result["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
            except:
                result["publicip"] = ""

            if "networkInterfaces" in result.keys():
                del(result["networkInterfaces"])

            print(json.dumps(result))

    except Exception as e:
        print("error: {}".format(e))

if __name__ == "__main__":
    if (CredentialsFilePath == None):
        exit("CredentialsFilePath None ERROR")
    
    account, project_id = getLogin()
    
    if (Func == "Zone"):
        getZoneList(account, project_id)
        
    if (Func == "Image"):
        getImageList(account, project_id)
        
    if (Func == "MachineType"):
        getMachineTypeList(account, project_id)
    
    if (Func == "FirewallRule"):
        getFirewallRuleList(account, project_id)
    
    if (Func == "Instance"):
        getInstanceInfo(account, project_id)
    
    if (Func == "AllInstance"):
        getInstanceList(account, project_id)
    
    