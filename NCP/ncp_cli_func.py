import os
import re
import json
import argparse
import threading
import platform

lock = threading.Lock()
PLATFORM = platform.system()
parser = argparse.ArgumentParser()

parser.add_argument('--Func', dest="Func")
parser.add_argument('--Profile', dest="Profile")
parser.add_argument("--AccessKey", dest="AccessKey")
parser.add_argument("--SecretAccessKey", dest="SecretAccessKey")
parser.add_argument("--Region", dest="Region")
parser.add_argument("--ServerImageProductCode", dest="ServerImageProductCode")
parser.add_argument("--Name", dest="Name")

args = parser.parse_args()

Func = args.Func
Profile = args.Profile
AccessKey = args.AccessKey
SecretAccessKey = args.SecretAccessKey
Region = args.Region
ServerImageProductCode = args.ServerImageProductCode
Name = args.Name

# input
# Profile, AccessKey, SecretAccessKey
def getLogin():
    try:
        if PLATFORM == "Windows":
            config = os.popen("echo %USERPROFILE%\.ncloud\configure").read().rstrip("\n")
        else:
            config = os.popen("echo /root/.ncloud/configure").read().rstrip("\n")    

        lock.acquire()
        with open(config, mode='a') as f:
            f.write("\n\n[{}]".format(Profile))
            f.write("\nncloud_access_key_id = {}".format(AccessKey))
            f.write("\nncloud_secret_access_key = {}".format(SecretAccessKey))
            f.write("\nncloud_api_url = https://ncloud.apigw.ntruss.com")
        lock.release()
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey
def getRegion():
    """
    - list Region by user account
    [
        {
            "regionCode": "KR",
            "regionName": "Korea"
        },
        ...
    ]
    """
    try:
        command = "ncloud vserver getRegionList --profile \"{}\"".format(Profile)
        results = json.loads(os.popen(command).read())["getRegionListResponse"]
        print(json.dumps(results["regionList"]))
        
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region
def getImageList():
    """
    - list Images in the specified Region (only SW.VSVR.OS)
    - to create instance,
        - "productCode"
    [
        {
        "productCode": "SW.VSVR.OS.LNX64.CNTOS.0703.B050",
        "productName": "centos-7.3-64",
        "productType": {
            "code": "LINUX",
            "codeName": "Linux"
        },
        "productDescription": "CentOS 7.3 (64-bit)",
        "infraResourceType": {
            "code": "SW",
            "codeName": "Software"
        },
        "cpuCount": 0,
        "memorySize": 0,
        "baseBlockStorageSize": 53687091200,
        "platformType": {
            "code": "LNX64",
            "codeName": "Linux 64 Bit"
        },
        "osInformation": "CentOS 7.3 (64-bit)",
        "dbKindCode": "",
        "addBlockStorageSize": 0,
        "generationCode": ""
        },
        ...
    ]
    
    """
    try:
        results = []
        command = "ncloud vserver getServerImageProductList --profile \"{}\" --regionCode \"{}\" --platformTypeCodeList LNX64 WND64 UBD64 UBS64".format(Profile,Region)
        tmp = json.loads(os.popen(command).read())["getServerImageProductListResponse"]
        
        for i in tmp["productList"]:
            if re.match("SW.VSVR.OS.*", i["productCode"]):
                results.append(i)
            
        print(json.dumps(results))
        
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, ServerImageProductCode
def getProductCodeList():
    """
    - After choose an image, list ProductCode by the Image
    - to create instance,
        - cpu count <- "cpuCount"
        - memory size <- "memorySize"
        - productType <- "productType.code" (HICPU/STAND/HIMEM/GPU/CPU)
        - machinetype <- "productCode"
    [
        {
        "productCode": "SVR.VSVR.HICPU.C002.M004.NET.HDD.B050.G002",
        "productName": "vCPU 2EA, Memory 4GB, Disk 50GB",
        "productType": {
            "code": "HICPU",
            "codeName": "High CPU"
        },
        "productDescription": "vCPU 2EA, Memory 4GB, Disk 50GB",
        "infraResourceType": {
            "code": "VSVR",
            "codeName": "Server (VPC)"
        },
        "cpuCount": 2,
        "memorySize": 4294967296,
        "baseBlockStorageSize": 53687091200,
        "osInformation": "",
        "diskType": {
            "code": "NET",
            "codeName": "Network Storage"
        },
        "dbKindCode": "",
        "addBlockStorageSize": 0,
        "generationCode": "G2"
        },
    ]
    """
    try:
        command = "ncloud vserver getServerProductList --profile \"{}\" --regionCode \"{}\" --serverImageProductCode \"{}\"".format(Profile,Region,ServerImageProductCode)
        results = json.loads(os.popen(command).read())["getServerProductListResponse"]
        print(json.dumps(results["productList"]))
        
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region
def getSubnetList():
    """
    - print Public&General Subnet List by the specified Region
    - to create instance,
        - subnet_id <- "subnetNo"
    [
        {
        "subnetNo": "57974",
        "vpcNo": "27074",
        "zoneCode": "KR-2",
        "subnetName": "js-subnet",
        "subnet": "192.168.0.0/24",
        "subnetStatus": {
            "code": "RUN",
            "codeName": "run"
        },
        "createDate": "2022-09-28T10:56:16+0900",
        "subnetType": {
            "code": "PUBLIC",
            "codeName": "Public"
        },
        "usageType": {
            "code": "GEN",
            "codeName": "General"
        },
        "networkAclNo": "41773"
        },
        ...
    ]
    """
    try:
        command = "ncloud vpc getSubnetList --profile {} --regionCode {} --subnetTypeCode PUBLIC --usageTypeCode GEN --subnetStatusCode RUN".format(Profile, Region) 
        results = json.loads(os.popen(command).read())["getSubnetListResponse"]
        print(json.dumps(results["subnetList"]))

    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region
def getInitScriptList():
    """
    - list InitSripts for Linux and Windows
    - to create instance,
        - userdata <- "initScriptName"
    [
        {
            "initScriptNo": "22244",
            "initScriptName": "lin-yj",
            "createDate": "2022-10-05T16:07:43+0900",
            "initScriptDescription": "",
            "initScriptContent": "",
            "osType": {
                "code": "LNX",
                "codeName": "LINUX"
            }
        },
        ....
    ]
    """
    try:
        results = []
        # Init script for Linux
        command = "ncloud vserver getInitScriptList --profile \"{}\" --regionCode \"{}\" --osTypeCode LNX".format(Profile,Region)
        tmp = json.loads(os.popen(command).read())["getInitScriptListResponse"]
        if len(tmp["initScriptList"]) > 0:
            results.extend(tmp["initScriptList"])
            
        # Init script for Windows
        command = "ncloud vserver getInitScriptList --profile \"{}\" --regionCode \"{}\" --osTypeCode WND".format(Profile,Region)
        tmp = json.loads(os.popen(command).read())["getInitScriptListResponse"]
        if len(tmp["initScriptList"]) > 0:
            results.extend(tmp["initScriptList"])
             
        print(json.dumps(results))
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region
def getInstaceList():
    """
    - list Instnace info by Region (If there is no instance, print [])
    - serverInstanceStatusName: init -> creating -> booting -> setting up -> running -> shutting down -> stopped -> terminating -> []
    [
        {
            "serverName": "lin-yj",
            "publicIp": "",
            "serverInstanceStatusName": "setting up",
            "regionCode": "KR"
        }
    ]
    """
    try:
        command = "ncloud vserver getServerInstanceList --profile \"{}\" --regionCode \"{}\"".format(Profile,Region)
        p = os.popen(command).read()
        results = json.loads(p)["getServerInstanceListResponse"]
    
        vm_info_list = []
        for i in results["serverInstanceList"]:
            vm_info = {}
            vm_info["serverName"] = i["serverName"]
            vm_info["publicIp"] = i["publicIp"]
            vm_info["serverInstanceStatusName"] = i["serverInstanceStatusName"]
            vm_info["regionCode"] = i["regionCode"]
            vm_info_list.append(vm_info)
        
        print(json.dumps(vm_info_list))
        
    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, Name
def getInstaceInfo():
    """
    - print Instnace info by Name (If the instance does not exist, print {})
    - serverInstanceStatusName: init -> creating -> booting -> setting up -> running -> shutting down -> stopped -> terminating -> {}
    {
        "serverName": "lin-yj",
        "publicIp": "",
        "serverInstanceStatusName": "running",
        "regionCode": "KR"
    }
    """
    try:
        command = "ncloud vserver getServerInstanceList --profile \"{}\" --regionCode \"{}\" --serverName \"{}\"".format(Profile, Region, Name)
        p = os.popen(command).read()
        results = json.loads(p)["getServerInstanceListResponse"]
        
        vm_info = {}
        for i in results["serverInstanceList"]:
            vm_info["serverName"] = i["serverName"]
            vm_info["publicIp"] = i["publicIp"]
            vm_info["serverInstanceStatusName"] = i["serverInstanceStatusName"]
            vm_info["regionCode"] = i["regionCode"]
            break
        
        print(json.dumps(vm_info))
        
    except Exception as e:
        print("error: ",e)

def deleteConfigure():
    """
    - delete .ncloud/configure file
    """
    try:
        lock.acquire()
        if PLATFORM == "Windows":
            config_file = os.popen("echo %USERPROFILE%\.ncloud\configure").read().rstrip("\n")
        else:
            config_file = os.popen("echo /root/.ncloud/configure").read().rstrip("\n")

        if os.path.isfile(config_file):
            os.remove(config_file)
        lock.release()
    except Exception as e:
        print("error: {}".format(e))

if __name__ == "__main__":
    if (Profile is None) or (AccessKey is None) or (SecretAccessKey is None):
        exit("Profile or AccessKey or SecretAccessKey None ERRO")
    
    getLogin()
    
    if (Func == "Region"):
        getRegion()
    
    if (Func == "Image"):
        getImageList()
        
    if (Func == "MachineType"):
        getProductCodeList()

    if (Func == "InitScript"):
        getInitScriptList()

    if (Func == "Subnet"):
        getSubnetList()    
    
    if (Func == "Instance"):
        getInstaceInfo()

    if (Func == "AllInstance"):
        getInstaceList()
    
    if (Func == "DeleteConfigure"):
        deleteConfigure()
    
    