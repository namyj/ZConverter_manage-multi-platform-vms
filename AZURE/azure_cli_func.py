import os
import json
import re
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--AppId", dest="AppId")
parser.add_argument("--Password", dest="Password")
parser.add_argument("--TenantId", dest="TenantId")
parser.add_argument("--Func", dest="Func")
parser.add_argument("--Region", dest="Region")
parser.add_argument("--OS", dest="OS")
parser.add_argument("--Name", dest="Name")

args = parser.parse_args()
AppId = args.AppId
Password = args.Password
TenantId = args.TenantId
Func = args.Func
Region = args.Region
OS = args.OS
Name = args.Name

PUBLISHER_DICT = {
    "Debian":"Debian",
    "CentOS":"OpenLogic",
    "Ubuntu":"Canonical",
    "Windows":"MicrosoftWindowsServer",
    "RHEL":"RedHat"
}

# input
# AppId, Password, TenantId
def getLogin():
    try:
        sub_id = None
        command = "az login --service-principal -u \"{}\" -p \"{}\" --tenant \"{}\" --only-show-errors".format(AppId, Password, TenantId)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            raise Exception(stderr)
        else:
            result = json.loads(stdout)
            sub_id = result[0]["id"]

        return sub_id
    except Exception as e:
        print("error: {}".format(e)) 

# input
# AppId, Password, TenantId
def getRegionList():
    """
    - list suppprted regions for the current subscription. (Can't use --subscription option)
    - to create instance
        - region <- "name"
    [
        {
            "displayname": "East US",
            "name": "eastus"
        },
        ...
    ]
    """
    try:
        command = "az account list-locations --query \"sort_by([].{displayname:displayName,name:name}, &name)\""
        p = os.popen(command).read()
        print(p)
    except Exception as e:
        print("error: {}".format(e))

# input
# AppId, Password, TenantId, Region
def getMachineTypeList(sub_id):
    """
    - list available sizes for VMs in the specified Region
    - to create instance
        - machine_type <- "name"
    [
        {
            "maxDataDiskCount": 2,
            "memoryInMb": 2048,
            "name": "Standard_A1_v2",
            "numberOfCores": 1,
            "osDiskSizeInMb": 1047552,
            "resourceDiskSizeInMb": 10240
        },
        ...
    ]
    """
    try:
        command = "az vm list-sizes --subscription \"{}\" -l \"{}\"".format(sub_id, Region)
        p = os.popen(command).read()
        print(p)
    except Exception as e:
        print("error: {}".format(e))

# input
# AppId, Password, TenantId, Region, OS
def getFilterImageList(sub_id):
    try:
        # get offer and sku
        command = "az vm image list --subscription \"{}\" --architecture x64 -f \"{}\" -p \"{}\" --location \"{}\" --all ".format(sub_id, OS, PUBLISHER_DICT[OS], Region) 
        command += "--query \"sort_by([].{\\\"publisher\\\":\\\"publisher\\\",\\\"offer\\\":\\\"offer\\\",\\\"sku\\\":\\\"sku\\\"}, &offer)\""
        results = json.loads(os.popen(command).read())
        
        # get only offer
        command = "az vm image list --subscription \"{}\" --architecture x64 -f \"{}\" -p \"{}\" --location \"{}\" --all --query \"[].offer\"".format(sub_id, OS, PUBLISHER_DICT[OS], Region)
        keys = set(json.loads(os.popen(command).read()))
        values = [[]]*len(keys)
        offer_dict = dict(zip(keys, values))

        final_result = []
        for sku in results:
            if sku["sku"] in offer_dict[sku["offer"]]:
                pass
            else:
                offer_dict[sku["offer"]].append(sku["sku"])
                final_result.append(sku)

        print(json.dumps(final_result))

    except Exception as e:
        print("error: {}".format(e))

# input
# AppId, Password, TenantId, Region
def getTotalImageList(sub_id):
    try:
        results = []
        for offer in list(PUBLISHER_DICT.keys()):
            if len(results) > 0:
                results.extend(getOfferList(sub_id, offer))
            else:
                results = getOfferList(sub_id, offer)

        print(json.dumps(results))     
    except Exception as e:
        print("error: {}".format(e))

# sub func
def getOfferList(sub_id, offer):
    try:
        # get offer and sku
        command = "az vm image list --subscription \"{}\" --architecture x64 -f \"{}\" -p \"{}\" --location \"{}\" --all ".format(sub_id, offer, PUBLISHER_DICT[offer], Region) 
        command += "--query \"sort_by([].{\\\"offer\\\":\\\"offer\\\",\\\"sku\\\":\\\"sku\\\"}, &offer)\""
        results = json.loads(os.popen(command).read())
        
        # get only offer
        command = "az vm image list --subscription \"{}\" --architecture x64 -f \"{}\" -p \"{}\" --location \"{}\" --all --query \"[].offer\"".format(sub_id, offer, PUBLISHER_DICT[offer], Region)
        keys = set(json.loads(os.popen(command).read()))
        values = [[]]*len(keys)
        offer_dict = dict(zip(keys, values))

        final_result = []
        for sku in results:
            if sku["sku"] in offer_dict[sku["offer"]]:
                pass
            else:
                offer_dict[sku["offer"]].append(sku["sku"])
                final_result.append(sku)

        return final_result

        # save JSON FILE
        # filename = ""
        # with open(filename, 'w') as f:
        #     json.dump(final_result, f,ensure_ascii=False, indent="\t")
    except Exception as e:
        print("error: {}".format(e))

# input
# AppId, Password, TenantId, Region, Name
def getInstanceInfo(sub_id):
    """
    - get Instance Info by Name (If ResourceNotFound or ResourceGroupNotFound occur, print {})
    - powerState : "" ->  "VM starting" -> "VM running" -> "" -> {}
    {
        "location": "koreasouth",
        "name": "zcm",
        "powerState": "VM running",
        "publicIps": "52.231.158.93",
        "resourceGroup": "ZConverter"
    }
    """
    try:
        RESOURCE_GROUP = Name.upper()+"-GROUP"
        command = "az vm show --subscription \"{}\" -g \"{}\" -n \"{}\" --show-details ".format(sub_id, RESOURCE_GROUP, Name)
        command += "--query \"{\\\"name\\\":\\\"name\\\",\\\"location\\\":\\\"location\\\",\\\"powerState\\\":\\\"powerState\\\",\\\"publicIps\\\":\\\"publicIps\\\",\\\"resourceGroup\\\":\\\"resourceGroup\\\"}\" --only-show-errors 2>&1"
        p = os.popen(command).read()

        if ("ResourceNotFound" in p) or ("ResourceGroupNotFound" in p) or ("NotFound" in p):
            print("{}")
        else:
            print(p)

    except Exception as e:
        print("error: {}".format(e))


# input
# AppId, Password, TenantId, Region, Name
def getInstanceList(sub_id):
    """
    - get Instance Info by Resource Group(Name) (If there is no instance, print [])  
    - powerState : "" ->  "VM starting" -> "VM running" -> "" -> {}
    [
        {
            "location": "koreasouth",
            "name": "zcm",
            "powerState": "VM running",
            "publicIps": "52.231.158.93",
            "resourceGroup": "ZConverter"
        },
        ...
    ]
    """
    try:
        RESOURCE_GROUP = Name.upper()+"-GROUP"

        # get Instance ID
        command = "az vm list --subscription \"{}\" -g \"{}\" --query \"[].id\" -o json --only-show-errors".format(sub_id, RESOURCE_GROUP)
        p = os.popen(command).read()

        if "ResourceGroupNotFound" in p:
            print([])
        else:
            result = json.loads(p)
            
            if len(result) == 0:
                print([])
            else:
                # get Instance Info List
                ids = ' '.join(op for op in result)
                command = "az vm show -d --ids {} ".format(ids)
        
                if len(result) == 1:
                    command += "--query \"{\\\"name\\\":\\\"name\\\",\\\"location\\\":\\\"location\\\",\\\"powerState\\\":\\\"powerState\\\",\\\"publicIps\\\":\\\"publicIps\\\",\\\"resourceGroup\\\":\\\"resourceGroup\\\"}\" --only-show-errors"
                    p = os.popen(command).read()
                    print("[\n{}]".format(p))
                else:
                    command += "--query \"[].{\\\"name\\\":\\\"name\\\",\\\"location\\\":\\\"location\\\",\\\"powerState\\\":\\\"powerState\\\",\\\"publicIps\\\":\\\"publicIps\\\",\\\"resourceGroup\\\":\\\"resourceGroup\\\"}\" --only-show-errors"        
                    p = os.popen(command).read()
                    print(p)

    except Exception as e:
        print("error: {}".format(e))

if __name__ == "__main__":
    if (AppId is None) or (Password is None) or (TenantId is None):
        exit("AppId or Password or TenantId None ERROR")
    
    sub_id = getLogin()

    if (Func == "Region"):
        getRegionList()
    
    if (Func == "MachineType"):
        getMachineTypeList(sub_id)
    
    if (Func == "Image"):
        getFilterImageList(sub_id)

    if (Func == "TotalImageList"):
        getTotalImageList(sub_id)
    
    if (Func == "Instance"):
        getInstanceInfo(sub_id)
    
    if (Func == "AllInstance"):
        getInstanceList(sub_id)
