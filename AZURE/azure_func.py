import os
import json
import threading
import platform
import subprocess
import sys
import logging

PLATFORM = platform.system()
lock = threading.Lock()


PRIVATE_SOURCE_IP = "***.***.***.***/32" # must change to your private IP
PRIVATE_IN_PORTS = "22 3389 3306"
NSG_SOURCE_IP = "*" # ALL
NSG_IN_PORTS = "80 111 139 443 445 2049 3000 4001 5001 9051 9052 9053 9054 50001 50002 50005 53306"

class StreamToLogger(object):
   def __init__(self, logger, stream=sys.stdout, log_level=logging.INFO):
      self.logger = logger
      self.stream = stream
      self.log_level = log_level
      self.linebuf = ''

   def write(self, buf):
      self.stream.write(buf)
      self.linebuf += buf
      if buf=='\n':
          self.flush()

   def flush(self):
      for line in self.linebuf.rstrip().splitlines():
         self.logger.log(self.log_level, line.rstrip())
      self.linebuf = ''
      self.stream.flush()
      for handler in self.logger.handlers:
          handler.flush()

def sys_logger(*args, **kwargs):
    """
    Converts all print, raise statements to log to a file
    This function accepts all arguments to logging.basicConfig()
    """
    logging.basicConfig( *args, **kwargs)

    stdout_logger = logging.getLogger('STDOUT')
    sl = StreamToLogger(stdout_logger, sys.stdout, logging.INFO)
    sys.stdout = sl

    stderr_logger = logging.getLogger('STDERR')
    sl = StreamToLogger(stderr_logger, sys.stderr, logging.ERROR)
    sys.stderr = sl

def excepthook(args: threading.ExceptHookArgs):
    """
    When an exception is raise in a thread, excepthook function is executed.
    """
    logging.error("exc_type:{},exc_value:{}".format(args.exc_type, args.exc_value))

def load_json(json_path):
    with open('{}'.format(json_path), 'r') as f:
        data = json.load(f)
    return data

def user_login(user_data):
    try:
        command = "az login --service-principal -u \"{APPID}\" -p \"{PWD}\" --tenant \"{TENANT}\" --only-show-errors".format(APPID=user_data["app_id"], PWD=user_data["app_pwd"], TENANT=user_data["tenant_id"])
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            raise Exception(stderr)
        else:
            result = json.loads(stdout)

            if len(result) > 0:
                return result[0]["id"]
            else:
                raise Exception("Login ERROR")
            
    except Exception as e:
        exit(e)

def create_resource_group(sub_id, region, vmname):
    try:
        resource_group = {
            "status":"",
            "name":""
        }

        resource_group["name"] = vmname.upper()+"-GROUP"
        command = "az group create --subscription \"{SUB_ID}\" -l \"{LOCATION}\" -n \"{RESOURCE_GROUP}\"".format(SUB_ID=sub_id, LOCATION=region,RESOURCE_GROUP=resource_group["name"])
        logging.info(command)
        
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            resource_group["status"] = "fail"
        else:
            result = json.loads(stdout)
            resource_group["status"] = "success"
            resource_group["name"] = result["name"]

        logging.info("RESOURCE_GROUP: {}".format(resource_group))
        return resource_group
        
    except Exception as e:
        exit(e)

def create_network_security_group(sub_id, region, resource_group, vm_name):
    """
    - Inbound Rules
    - SOURCE : PRIVATE_SOURCE_IP / TCP : 22 3389 3306
    - SOURCE : ALL / TCP : 80 8080 53306 139 445 443 111 50001 50002 50005 2049 3000 9051 9052 9053 9054
    """
    try:
        network_sg = {
            "status":"",
            "name":""
        }
        
        # create NSG
        network_sg["name"] = vm_name.upper()+"-NSG"
        command = "az network nsg create --subscription \"{SUB_ID}\" -l \"{LOCATION}\" -g \"{RESOURCE_GROUP}\" -n \"{NSG_NAME}\"".format(SUB_ID=sub_id, LOCATION=region, RESOURCE_GROUP=resource_group,NSG_NAME=network_sg["name"])
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
            network_sg["status"] = "fail"
        else:
            result = json.loads(stdout)["NewNSG"]
            network_sg["status"] = "success"
            network_sg["name"] = result["name"]

        # update NSG rule
        if network_sg["status"] == "success":
            private_rule_name = vm_name.upper()+"-PRIVATE-RULE"
            command = "az network nsg rule create --subscription \"{SUB_ID}\" -g \"{RESOURCE_GROUP}\" --nsg-name \"{NSG_NAME}\" -n \"{RULE_NAME}\"".format(SUB_ID=sub_id, RESOURCE_GROUP=resource_group, NSG_NAME=network_sg["name"], RULE_NAME=private_rule_name)
            command += " --access allow --protocol Tcp --direction Inbound --priority 100 --source-address-prefix \"{SOURCEIP}\" --source-port-range \"*\" --destination-address-prefix \"*\" --destination-port-range {INPORTS}".format(SOURCEIP=PRIVATE_SOURCE_IP, INPORTS=PRIVATE_IN_PORTS)
            logging.info(command)

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))

            rule_name = vm_name.upper()+"-RULE"
            command = "az network nsg rule create --subscription \"{SUB_ID}\" -g \"{RESOURCE_GROUP}\" --nsg-name \"{NSG_NAME}\" -n \"{RULE_NAME}\"".format(SUB_ID=sub_id, RESOURCE_GROUP=resource_group, NSG_NAME=network_sg["name"], RULE_NAME=rule_name)
            command += " --access allow --protocol Tcp --direction Inbound --priority 200 --source-address-prefix \"{SOURCEIP}\" --source-port-range \"*\" --destination-address-prefix \"*\" --destination-port-range {INPORTS}".format(SOURCEIP=NSG_SOURCE_IP, INPORTS=NSG_IN_PORTS)
            logging.info(command)

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))

        logging.info("NSG: {}".format(network_sg))
        return network_sg

    except Exception as e:
        exit(e)

def create_public_ip(sub_id, region, resource_group, vm_name): 
    try:
        public_ip = {
            "status":"",
            "name":""
        }
        public_ip["name"] = vm_name.upper()+"-IP"
        command = "az network public-ip create --subscription \"{SUB_ID}\" -l \"{LOCATION}\" -g \"{RESOURCE_GROUP}\" -n \"{PUBLICIP_NAME}\" --allocation-method Static --sku Standard --only-show-errors".format(SUB_ID=sub_id, LOCATION=region, RESOURCE_GROUP=resource_group, PUBLICIP_NAME=public_ip["name"])
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            public_ip["status"] = "fail"
        else:
            result = json.loads(stdout)["publicIp"]
            public_ip["status"] = "success"
            public_ip["name"] = result["name"]

        logging.info("PUBLIC_IP: {}".format(public_ip))
        return public_ip

    except Exception as e:
        exit(e)    


def create_vnetwork(sub_id, region, resource_group, nsg, vm_name):
    try:
        vnetwork = {
            "status":"",
            "name":"",
            "subnet":""
        }
        vnetwork["name"] = vm_name.upper()+"-VNET"
        vnetwork["subnet"] = vm_name.upper()+"-SUBNET"

        command = "az network vnet create --subscription \"{SUB_ID}\" -l \"{LOCATION}\" -g \"{RESOURCE_GROUP}\"".format(SUB_ID=sub_id, LOCATION=region, RESOURCE_GROUP=resource_group)
        command += " -n \"{VNET}\" --address-prefix 10.0.0.0/16 --subnet-name \"{SUBNET}\" --subnet-prefix 10.0.1.0/24 --nsg \"{NSG}\"".format(VNET=vnetwork["name"], SUBNET=vnetwork["subnet"], NSG=nsg)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            vnetwork["status"] = "fail"
        else:
            result = json.loads(stdout)["newVNet"]
            vnetwork["status"] = "success"
            vnetwork["name"] = result["name"]

            if len(result["subnets"]) > 0:    
                vnetwork["subnet"] = result["subnets"][0]["name"]
            else:
                logging.error("Subnet does not exist")

        logging.info("VNET: {}".format(vnetwork))
        return vnetwork
    except Exception as e:
        exit(e)

def find_amiid(OS, OS_version):
    """
    - PUBLISHER:OFFER:SKU:VERSION
    """
    OS_ = OS.lower()

    if "centos" in OS_:
        amiid = "OpenLogic:{}:{}:latest".format(OS, OS_version) 
    elif "windows" in OS_:
        amiid = "MicrosoftWindowsServer:{}:{}:latest".format(OS, OS_version)
    elif "ubuntu" in OS_:
        amiid = "Canonical:{}:{}:latest".format(OS, OS_version)
    elif "rhel" in OS_:
        amiid = "RedHat:{}:{}:latest".format(OS, OS_version)
    elif "debian" in OS_:
        amiid = "Debian:{}:{}:latest".format(OS, OS_version)
    else:
        exit("find_amiid fail")

    return amiid

def create_instance(sub_id, region, resource_group, vnet, subnet, pubIp, nsg, vm_data, USERPATH="."):
    try:
        command_list = []
        command_list.append("az vm create --subscription \"{}\" --resource-group \"{}\" -l \"{}\"".format(sub_id, resource_group, region))
        command_list.append("-n \"{}\" --tags \"vm\"=\"{}\"".format(vm_data["vm_name"], vm_data["vm_name"]))
        command_list.append("--vnet-name \"{}\" --subnet \"{}\" --nsg \"{}\" --public-ip-address \"{}\" --public-ip-address-allocation static".format(vnet, subnet, nsg, pubIp))

        if vm_data["OS"] and vm_data["OS_version"]:
            amiid = find_amiid(vm_data["OS"], vm_data["OS_version"])
            command_list.append("--image \"{}\"".format(amiid))
            command_list.append("--os-disk-delete-option delete --storage-sku StandardSSD_LRS") # StandardSSD_LRS

        if vm_data["machine_type"]:
            command_list.append("--size \"{}\"".format(vm_data["machine_type"]))

        if len(vm_data["volume"]) > 0:
            volume_list = ' '.join(str(op) for op in vm_data["volume"])
            disk_option = ""
            for i in range(len(vm_data["volume"])):
                if i == 0:
                    disk_option += "<data_disk>=Delete"
                else:
                    disk_option += " <data_disk{}>=Delete".format(i+1)
            
            command_list.append("--data-disk-sizes-gb {} --data-disk-delete-option \"{}\"".format(volume_list, disk_option))

        if vm_data["username"] and vm_data["password"]:
            command_list.append("--admin-username \"{}\" --admin-password \"{}\"".format(vm_data["username"], vm_data["password"]))
        
        # if vm_data["userdata"]:
        #     command_list.append("--custom-data \"{}/{}\"".format(USERPATH, vm_data["userdata"]))

        command_list.append("--nic-delete-option delete --only-show-errors")
        command = ' '.join(op for op in command_list)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()
        
        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            result = None
        else:
            result = json.loads(stdout)
            logging.info(result)
            
        return result

    except Exception as e:
        exit(e)

def describe_isntance(vm_data, RESOURCE_GROUP, result):
    try:
        info = {}
        info["name"] = result["id"].split("/")[-1]
        info["status"] = "success"
        info["publicip"] = result["publicIpAddress"]
        info["login"] = {"id":vm_data["username"], "password":vm_data["password"]}
        info["resource_group"] = RESOURCE_GROUP
    
        return info
    except Exception as e:
        exit(e)

def run_userdata(sub_id, resource_group, vm_name, userdata, USERPATH="."):
    """
    - run userdata after create instance (Because Azure support custom data(init script) for specific OS versions)
    """
    try:
        filepath = USERPATH+"/"+userdata
        if not os.path.isfile(filepath):
            logging.error("Userdata file does not exist")
            return "fail"

        exe_format = userdata.split(".")[-1]
        if exe_format == "ps1":
            COMMAND_ID_ = "RunPowerShellScript"
        else:
            COMMAND_ID_ = "RunShellScript"

        command = "az vm run-command invoke --subscription \"{SUB_ID}\" -g \"{RESOURCE_GROUP}\" -n \"{VMNAME}\" --command-id \"{COMMAND_ID}\" --scripts \"@{FILE}\"".format(SUB_ID=sub_id, RESOURCE_GROUP=resource_group, VMNAME=vm_name, COMMAND_ID=COMMAND_ID_, FILE=filepath)
        logging.info(command)
        
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return "fail"
        else:
            logging.info(stdout)
            return "success"
            
    except Exception as e:
        exit(e)

def delete_resource_group(sub_id, vm_name):
    try:
        resource_group = vm_name.upper()+"-GROUP"
        command = "az group delete --subscription \"{}\" -n \"{}\" --yes".format(sub_id, resource_group)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return "fail"
        else:
            logging.info(stdout)  
            return "success"  
    except Exception as e:
        exit(e)
