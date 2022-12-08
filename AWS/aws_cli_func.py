import os
import json
import argparse
import threading
import subprocess

lock = threading.Lock()
parser = argparse.ArgumentParser()

parser.add_argument('--Func', dest="Func")
parser.add_argument('--Profile', dest="Profile")
parser.add_argument("--AccessKey", dest="AccessKey")
parser.add_argument("--SecretAccessKey", dest="SecretAccessKey")
parser.add_argument("--Region", dest="Region")
parser.add_argument("--SelectRegion", dest="SelectRegion")
parser.add_argument("--Name", dest="Name")
parser.add_argument("--OS", dest="OS")
parser.add_argument("--OS_version", dest="OS_version")
parser.add_argument("--InstanceId", dest="InstanceId")

args = parser.parse_args()

Func = args.Func
Profile = args.Profile
AccessKey = args.AccessKey
Region = args.Region
SecretAccessKey = args.SecretAccessKey
SelectRegion = args.SelectRegion
Name = args.Name
OS = args.OS
OS_version = args.OS_version
InstanceId = args.InstanceId

# input 
# Profile, AccessKey, SecretAccessKey, Region
def checkLogin():
    try:
        login_info = {}
        login_info["aws_access_key_id"] = AccessKey
        login_info["aws_secret_access_key"] = SecretAccessKey
        login_info["region"] = Region

        login_check = True
        command_list = {}
        command_list["aws_access_key_id"] = "aws configure get aws_access_key_id --profile \"{}\"".format(Profile)
        command_list["aws_secret_access_key"] = "aws configure get aws_secret_access_key --profile \"{}\"".format(Profile)
        command_list["region"] = "aws configure get region --profile \"{}\"".format(Profile)
        
        for key, command in command_list.items():
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                login_check = False
                break
            else:
                result = stdout.strip("\n")
                if login_info[key] == result:
                    login_check = True
                else:
                    login_check = False
                    break
        
        return login_check

    except Exception as e:
        print("error : ",e)

# input 
# Profile, AccessKey, SecretAccessKey, Region
def getLogin():
    try:   
        limit = 0
        flag = True

        while flag:
            limit += 1

            lock.acquire()
            os.system("aws configure set aws_access_key_id \"{}\" --profile \"{}\"".format(AccessKey, Profile)) 
            os.system("aws configure set aws_secret_access_key \"{}\" --profile \"{}\"".format(SecretAccessKey, Profile)) 
            os.system("aws configure set region \"{}\" --profile \"{}\"".format(Region, Profile))
            lock.release()

            # check login
            command = "aws ec2 describe-instances --profile \"{}\"".format(Profile)
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                if "Unable to parse config file: /root/.aws/credentials" in stderr:
                    deleteConfigure()
                flag = True
            else:
                flag = False
                
            if limit > 10:
                exit("aws cli login fail (limit exceed)")

    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region
def getRegion():
    try:
        command = "aws ec2 describe-regions --profile \"{}\"".format(Profile)
        results = json.loads(os.popen(command).read())
        print(json.dumps(results["Regions"]))
        
    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion
def getMachineTypeList():
    """
    - print Machine type List
        Name=hypervisor,Values=xen
        Name=supported-virtualization-type,Values=hvm
        Name=processor-info.supported-architecture,Values=x86_64
        # Name=network-info.ena-support,Values=supported 
        Name=supported-root-device-type,Values=ebs
    """
    try:
        # command = "aws ec2 describe-instance-types --profile \"{}\" --region \"{}\" --filters \"Name=hypervisor,Values=xen\" \"Name=supported-virtualization-type,Values=hvm\" \"Name=processor-info.supported-architecture,Values=x86_64\" \"Name=network-info.ena-support,Values=supported\" \"Name=supported-root-device-type,Values=ebs\"".format(Profile, SelectRegion)
        command = "aws ec2 describe-instance-types --profile \"{}\" --region \"{}\" --filters \"Name=hypervisor,Values=xen\" \"Name=supported-virtualization-type,Values=hvm\" \"Name=processor-info.supported-architecture,Values=x86_64\" \"Name=supported-root-device-type,Values=ebs\"".format(Profile, SelectRegion)
        results = json.loads(os.popen(command).read())
        print(json.dumps(results["InstanceTypes"]))     
    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion
def getVpcList():
    """
    [
        {
            "VpcId": "vpc-01decc820913f6270",
            "SecurityGroup": [
                {
                    "GroupId": "sg-0479d510c1aff0954",
                    "GroupName": "default"
                },
                {
                    "GroupId": "sg-00c7f6297192073ba",
                    "GroupName": "user-service-20220608050759384000000001"
                }
            ]
        },
    ]
    """
    try:
        command = "aws ec2 describe-vpcs --profile \"{}\" --region \"{}\" --filters \"Name=state,Values=available\"".format(Profile, SelectRegion)
        command += " --query \"sort_by(Vpcs, &VpcId)[].{VpcId:VpcId}\""
        p = os.popen(command).read()
        try:
            results = json.loads(p)

            for vpc in results:
                vpc["SecurityGroup"] = getSecurityGroupList(vpc["VpcId"])

            print(json.dumps(results))
        except:
            print([])
            
    except Exception as e:
        print("error : ",e)

# subfunc
def getSecurityGroupList(vpcid):
    try:
        command =  "aws ec2 describe-security-groups --profile \"{}\" --region \"{}\" --filters \"Name=vpc-id,Values={}\"".format(Profile, SelectRegion, vpcid)
        command += " --query \"sort_by(SecurityGroups, &GroupName)[].{GroupId:GroupId,GroupName:GroupName}\""

        try:
            results = json.loads(os.popen(command).read())
            return results
        except:
            return []
    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion
def getImageList():
    """
    - list all of Images in aws-marketplace and user account
    - filter
        Name=virtualization-type,Values=hvm
        Name=architecture,Values=x86_64
        Name=hypervisor,Values=xen
        # Name=ena-support,Values=true
        Name=root-device-type,Values=ebs
        Name=state,Values=available
        Name=image-type,Values=machine
    """
    try:
        # Image from amazon & aws-marketplace
        command = "aws ec2 describe-images --profile \"{}\" --region \"{}\" --owners amazon aws-marketplace --filters \"Name=virtualization-type,Values=hvm\" \"Name=architecture,Values=x86_64\" \"Name=hypervisor,Values=xen\" \"Name=is-public,Values=true\" \"Name=root-device-type,Values=ebs\" \"Name=state,Values=available\" \"Name=image-type,Values=machine\"".format(Profile, SelectRegion)
        command += " --query \"sort_by(Images, &Name)[].{Name:Name,ImageId:ImageId,ImageLocation:ImageLocation,OwnerId:OwnerId,PlatformDetails:PlatformDetails,Description:Description}\""
        results = json.loads(os.popen(command).read())
        
        # Image from user
        command = "aws ec2 describe-images --profile \"{}\" --region \"{}\" --executable-users self --filters \"Name=virtualization-type,Values=hvm\" \"Name=architecture,Values=x86_64\" \"Name=hypervisor,Values=xen\" \"Name=root-device-type,Values=ebs\" \"Name=state,Values=available\" \"Name=image-type,Values=machine\"".format(Profile, SelectRegion)
        command += " --query \"sort_by(Images, &Name)[].{Name:Name,ImageId:ImageId,ImageLocation:ImageLocation,OwnerId:OwnerId,PlatformDetails:PlatformDetails,Description:Description}\""
        results.extend(json.loads(os.popen(command).read()))
        
        print(json.dumps(results))    
         
    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion, OS, OS_version
def getFilterImageList():
    """
    - list Images about the specified OS and OS_version 
    """
    try:
        osinfo = OS.lower() + OS_version.lower()

        name_filter = ""
        if osinfo == "debian8":
            name_filter = "*debian-8*\"" 
        elif osinfo == "debian9":
            name_filter = "*debian-stretch*\"" 
        elif osinfo == "debian10":
            name_filter = "*debian-10-amd64*,*debian-10*\""
        elif osinfo == "debian11":
            name_filter = "*debian-11-amd64*,*debian-11*\""
        elif osinfo == "debian12": 
            name_filter = "*debian-12*\""
        elif osinfo == "amazonlinux414":
            name_filter = "*amzn2-ami*2.0*,*amazonlinux2*,*amazonlinux-2*\""
        elif osinfo == "amazonlinux510":
            name_filter = "*amzn2-ami*5.10*\""
        elif osinfo == "ubuntu1404":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-trusty-14.04-amd64*,*ubuntu-trusty-14.04*\""
        elif osinfo == "ubuntu1604":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-xenial-16.04-amd64*,*ubuntu-xenial-16.04*\""
        elif osinfo == "ubuntu1804":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-bionic-18.04-amd64*,*ubuntu-bionic-18.04*\""
        elif osinfo == "ubuntu1810":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-cosmic-18.10-amd64*,*ubuntu-cosmic-18.10*\""
        elif osinfo == "ubuntu1904":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-disco-19.04-amd64*,*ubuntu-disco-19.04*\""
        elif osinfo == "ubuntu2004":
            name_filter = "*ubuntu*/images/hvm-ssd/ubuntu-focal-20.04-amd64*,*ubuntu-focal-20.04*\""
        elif osinfo == "ubuntu2204":
            name_filter =  "*ubuntu*/images/hvm-ssd/ubuntu-jammy-22.04-amd64*,*ubuntu-jammy-22.04*\""
        elif osinfo == "centos6":
            name_filter =  "*CentOS*Linux*6*x86_64*HVM*EBS*,*CentOS Linux 6*,*CentOS*6*x86_64*\""
        elif osinfo == "centos7":
            name_filter =  "*CentOS*Linux*7*x86_64*HVM*EBS*,*CentOS Linux 7*,*CentOS*7*x86_64*\""
        elif osinfo == "centos8":
            name_filter =  "*CentOS*Linux*8*x86_64*HVM*EBS*,*CentOS*Stream*8*,*CentOS*8*x86_64*\""
        elif osinfo == "rhel6":
            name_filter =  "*RHEL-6*,*RHEL*6*x86_64*,*rhel-6*,*rhel*6*x86_64*\""
        elif osinfo == "rhel7":
            name_filter =  "*RHEL-7*,*RHEL*7*x86_64*,*rhel-7*,*rhel*7*x86_64*\""
        elif osinfo == "rhel8":
            name_filter =  "*RHEL-8*,*RHEL*8*x86_64*,*rhel-8*,*rhel*8*x86_64*\""
        elif osinfo == "rhel9":
            name_filter =  "*RHEL-9*,*RHEL*9*x86_64*,*rhel-9*,*rhel*9*x86_64*\""
        elif osinfo == "windows2022":
            name_filter =  "*Windows_Server-2022-English-Full-Base-*\""
        elif osinfo == "windows2019":
            name_filter =  "*Windows_Server-2019-English-Full-Base-*\""
        elif osinfo == "windows2016":
            name_filter =  "*Windows_Server-2016-English-Full-Base-*\""
        elif osinfo == "windows2012":
            name_filter =  "*Windows_Server-2012-RTM-English-Full-Base-*\""
        elif osinfo == "windows2012r2":
            name_filter =  "*Windows_Server-2012-R2_RTM-English-64Bit-Base-*\""
        elif osinfo == "windows2008":
            name_filter =  "*Windows_Server-2008-R2_SP1-English-64Bit-Base-*\""

        command = "aws ec2 describe-images --profile \"{}\" --region \"{}\" --owners amazon aws-marketplace".format(Profile, SelectRegion)
        command += " --filters \"Name=virtualization-type,Values=hvm\" \"Name=architecture,Values=x86_64\" \"Name=hypervisor,Values=xen\" \"Name=is-public,Values=true\" \"Name=root-device-type,Values=ebs\" \"Name=state,Values=available\" \"Name=image-type,Values=machine\" \"Name=name,Values={}".format(name_filter)
        command += " --query \"sort_by(Images, &Name)[].{Name:Name,ImageId:ImageId,ImageLocation:ImageLocation,OwnerId:OwnerId,PlatformDetails:PlatformDetails,Description:Description}\""
        results = json.loads(os.popen(command).read())

        command = "aws ec2 describe-images --profile \"{}\" --region \"{}\" --executable-users self".format(Profile, SelectRegion)
        command += " --filters \"Name=virtualization-type,Values=hvm\" \"Name=architecture,Values=x86_64\" \"Name=hypervisor,Values=xen\" \"Name=root-device-type,Values=ebs\" \"Name=state,Values=available\" \"Name=image-type,Values=machine\" \"Name=name,Values={}".format(name_filter)
        command += " --query \"sort_by(Images, &Name)[].{Name:Name,ImageId:ImageId,ImageLocation:ImageLocation,OwnerId:OwnerId,PlatformDetails:PlatformDetails,Description:Description}\""
        results.extend(json.loads(os.popen(command).read()))

        print(json.dumps(results))  
    except Exception as e:
        print("error : ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion
def getInstanceList():
    """
    - print all of Instances in the specified region (If there is no Instance, print [])
    - State : pending -> running -> stopping -> stopped -> shutting-down -> terminated
    [
        {
            "AvailabilityZone": "ap-northeast-2c",
            "PublicIpAddress": "13.125.44.222",
            "State": "running",
            "Name": "aws-source-rhel"
        },
        ....
    ]
    """
    try:
        command = "aws ec2 describe-instances --profile \"{}\" --region \"{}\" ".format(Profile, SelectRegion)
        command += "--query \"Reservations[*].sort_by(Instances, &LaunchTime)[].{AvailabilityZone:Placement.AvailabilityZone,PublicIpAddress:PublicIpAddress,State:State.Name,Name:Tags[?Key=='Name'].Value|[0]}\""
        results = os.popen(command).read()
        print(results)

    except Exception as e:
        print("error: ",e)

# input
# Profile, AccessKey, SecretAccessKey, Region, SelectRegion, Name, InstanceId
def getInstanceInfo():
    """
    - list Instances info by Name in the specified Region (If the Instance does not exist, print [])
    - State : pending -> running -> stopping -> stopped -> shutting-down -> terminated
    - case1: InstanceId is not None, Instance Info exist -> list the Instance Info which have same Instance Id
    - case2: InstanceId is not None, Instane Info does not exist -> print []
    - case3: InstanceId is None -> list all Instance Info which have same name.
    # case 1
    [
        {
            "Name": "aws-test",
            "InstanceId": "i-0f8e3f311d7233077",
            "AvailabilityZone": "ap-northeast-2c",
            "PublicIpAddress": "52.79.241.238",
            "State": "running"
        }
    ]
    # case 2
    []
    # case 3
    [
        {
            "Name": "aws-test",
            "InstanceId": "i-0c81837db323d1d54",
            "AvailabilityZone": "ap-northeast-2c",
            "PublicIpAddress": "15.164.98.221",
            "State": "running"
        },
        {
            "Name": "aws-test",
            "InstanceId": "i-0f8e3f311d7233077",
            "AvailabilityZone": "ap-northeast-2c",
            "PublicIpAddress": "52.79.241.238",
            "State": "running"
        }
    ]
    """
    try:
        final_result = []
        command = "aws ec2 describe-instances --profile \"{}\" --region \"{}\" --filters Name=tag:Name,Values=\"{}\" ".format(Profile, SelectRegion, Name)
        command += "--query \"Reservations[*].sort_by(Instances, &LaunchTime)[].{Name:Tags[?Key=='Name'].Value|[0],InstanceId:InstanceId,AvailabilityZone:Placement.AvailabilityZone,PublicIpAddress:PublicIpAddress,State:State.Name}\""

        p = os.popen(command).read()
        try:
            results = json.loads(p)
            for i in results:
                if i["InstanceId"] == InstanceId:
                    final_result.append(i)
                    break
            
            if InstanceId:
                print(json.dumps(final_result))
            else:
                print(json.dumps(results))
        except:
            print([])

    except Exception as e:
        print("error: {}".format(e))

# Temp func
def deleteConfigure():
    """
    - delete .aws/config , .aws/credentials file
    """
    import platform
    PLATFORM = platform.system() # Windows , Linux

    lock.acquire()
    if PLATFORM == "Windows":
        config_file = os.popen("echo %USERPROFILE%\.aws\config").read().rstrip("\n")
        credentials_file = os.popen("echo %USERPROFILE%\.aws\credentials").read().rstrip("\n")
    else:
        config_file = os.popen("echo /root/.aws/config").read().rstrip("\n")
        credentials_file = os.popen("echo /root/.aws/credentials").read().rstrip("\n")

    if os.path.isfile(config_file):
        os.remove(config_file)

    if os.path.isfile(credentials_file):
        os.remove(credentials_file)
    lock.release()

if __name__ == "__main__":
    if (Profile == None) or (AccessKey == None) or (SecretAccessKey == None):
        exit("Profile or AccessKey or SecretAccessKey None ERROR")
    
    if (Func == "DeleteConfigure"):
        deleteConfigure()
        
    if not checkLogin():
        getLogin()
    
    if (Func == "Region"):
        getRegion()
        
    if (Func == "MachineType"):
        getMachineTypeList()

    if (Func == "SecurityGroup"):
        getVpcList()

    if (Func == "Image"):
        getImageList()
        # getFilterImageList()
    
    if (Func == "FilterImage"):
        getFilterImageList()
    
    if (Func == "Instance"):
        getInstanceInfo()

    if (Func == "AllInstance"):
        getInstanceList()
    
