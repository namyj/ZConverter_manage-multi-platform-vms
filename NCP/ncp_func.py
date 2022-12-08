import os
import json
import threading
from time import sleep
import subprocess
import platform
import sys
import logging

PLATFORM = platform.system() # Windows , Linux
lock = threading.Lock()

OS_DICT = {
    "centos":"CNTOS",
    "ubuntu":"UBNTU",
    "linux":"UBNTU",
    "windows":"WND"
}

PLATFORM_TYPE = {
    "CNTOS":"LNX64",
    "UBNTU":"LNX64",
    "WND":"WND64"
}

OS_VERSION_DICT = {
    "CNTOS-7.3":"0703",
    "CNTOS-7.8":"0708",
    "UBNTU-18.04":"SVR1804",
    "UBNTU-20.04":"SVR2004",
    "WND-2016":"SVR2016EN",
    "WND-2019":"SVR2019EN"
}

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
        if PLATFORM == "Windows":
            conf_file = os.popen("echo %USERPROFILE%\.ncloud\configure").read().rstrip("\n")
        else:
            conf_file = os.popen("echo /root/.ncloud/configure").read().rstrip("\n")
            
        profile = user_data["profile"]
        acc_key = user_data["access_key"]
        sec_acc_key = user_data["secret_access_key"]
        
        lock.acquire()
        with open(conf_file, mode='a') as f:
            f.write("\n\n[{}]".format(profile))
            f.write("\nncloud_access_key_id = {}".format(acc_key))
            f.write("\nncloud_secret_access_key = {}".format(sec_acc_key))
            f.write("\nncloud_api_url = https://ncloud.apigw.ntruss.com")
        lock.release()

        return profile
    except Exception as e:
        exit(e)

def find_image(OS, Version):
    OS_ = OS_DICT[OS.lower()]
    platform_type = PLATFORM_TYPE[OS_]
    Version_ = OS_VERSION_DICT[OS_+"-"+Version]

    if platform_type == "WND64":
        boot_size = "B100"
    else:
        boot_size = "B050"
        
    img_code = "SW.VSVR.OS.{platform_type}.{os}.{version}.{boot_size}".format(platform_type=platform_type,os=OS_,version=Version_,boot_size=boot_size)

    return img_code

def find_ProcutCode(profile, region, img_code, cpu_count, memory_size, DISKTYPE="SSD"):
    try:
        GBYTE = 1024**3
        pcode = None
        command = "ncloud vserver getServerProductList --profile \"{}\" --regionCode \"{}\" --serverImageProductCode \"{}\" --generationCode G2".format(profile, region, img_code) # G1 or G2
        logging.info(command)
        
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)["getServerProductListResponse"]["productList"]
            
            for i in range(len(result)):
                if (cpu_count == result[i]["cpuCount"]) and (memory_size == result[i]["memorySize"]//GBYTE):
                    disk_type = result[i]["productCode"].split(".")[-3]
                    if DISKTYPE == disk_type:
                        pcode = result[i]["productCode"]
        
        return pcode

    except Exception as e:
        exit(e)

def find_vpc_acg(profile, region, subnet_id):
    try:
        # VPC
        vpcNo = None
        command = "ncloud vpc getSubnetDetail --profile \"{}\" --regionCode \"{}\" --subnetNo \"{}\"".format(profile, region, subnet_id)
        logging.info(command)

        p = os.popen(command).read()
        subnet_list = json.loads(p)["getSubnetDetailResponse"]["subnetList"]
        if len(subnet_list) > 0:
            vpcNo = subnet_list[0]["vpcNo"]
        else:
            raise Exception("find_vpc fail")

        # ACG
        acgNo = None
        command = "ncloud vserver getAccessControlGroupList --profile \"{}\" --regionCode \"{}\" --vpcNo \"{}\" --accessControlGroupStatusCode RUN".format(profile, region, vpcNo)
        logging.info(command)

        p = os.popen(command).read()
        acg_list = json.loads(p)["getAccessControlGroupListResponse"]["accessControlGroupList"]
        if len(acg_list) > 0:
            acgNo = acg_list[0]["accessControlGroupNo"]
        else:
            raise Exception("find_acg fail")
        
        return vpcNo, acgNo
    
    except Exception as e:
        exit(e)

def check_keypair(profile, keyname):
    try: 
        command = "ncloud vserver getLoginKeyList --profile \"{}\" --keyName \"{}\"".format(profile, keyname)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            result = 0
        else:
            result = json.loads(stdout)["getLoginKeyListResponse"]["totalRows"]

        return result

    except Exception as e:
        exit(e)

def get_initscriptNo(profile, region, init_script):
    try:
        initNo = None
        command = "ncloud vserver getInitScriptList --profile \"{}\" --regionCode \"{}\" --initScriptName \"{}\"".format(profile, region, init_script)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)["getInitScriptListResponse"]["initScriptList"]

            for i in range(len(result)):
                if init_script == result[i]["initScriptName"]:
                    initNo = result[i]["initScriptNo"]
                    break

        return initNo

    except Exception as e:
        exit(e)

def create_instance(profile, region, vm_data): 
    serverNo = None
    command_list = []
    command_list.append("ncloud vserver createServerInstances --profile \"{}\"".format(profile))
    command_list.append("--feeSystemTypeCode MTRAT --associateWithPublicIp true --regionCode \"{}\"".format(region))
    command_list.append("--serverName \"{}\"".format(vm_data["vm_name"]))
        
    # Image
    if vm_data["OS"] and vm_data["OS_version"]:
        img_code = find_image(vm_data["OS"], vm_data["OS_version"])
        if img_code is not None:
            command_list.append("--serverImageProductCode \"{}\"".format(img_code))
        
    # Product Code
    if vm_data["cpu_count"] and vm_data["memory_size"]:
        p_code = find_ProcutCode(profile, region, img_code, int(vm_data["cpu_count"]), int(vm_data["memory_size"]))
        if p_code is not None:
            command_list.append("--serverProductCode \"{}\"".format(p_code))
        
    # Login Key
    if vm_data["loginkey"] and (check_keypair(profile, vm_data["loginkey"]) > 0):
        command_list.append("--loginKeyName \"{}\"".format(vm_data["loginkey"]))
    
    # Subnet, VPC, ACG
    if vm_data["subnet_id"]:
        vpcNo, acgNo = find_vpc_acg(profile, region, vm_data["subnet_id"])
        command_list.append("--subnetNo \"{}\"".format(vm_data["subnet_id"]))
        command_list.append("--vpcNo \"{}\"".format(vpcNo))
        command_list.append("--networkInterfaceList \"networkInterfaceOrder=\'0\', accessControlGroupNoList=[\'{}\']\"".format(acgNo))

    # userdata(init script)
    if vm_data["userdata"]:
        initNo = get_initscriptNo(profile, region, vm_data["userdata"])
        if initNo is not None:
            command_list.append("--initScriptNo {}".format(initNo))
    
    command = ' '.join(op for op in command_list)
    logging.info(command)

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    stdout, stderr = proc.communicate()

    if proc.returncode:
        logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
    else:
        result = json.loads(stdout)["createServerInstancesResponse"]["serverInstanceList"]
        if len(result) > 0:
            serverNo = result[0]["serverInstanceNo"]

    return serverNo

def attach_block(profile, region, serverNo, volume):
    """
    - Attach Block Volume
    - Naming rule: ncp-{serverNo}-{count}  (ex) ncp-12345-0
    """
    try:
        for i in range(len(volume)):        
            name = "ncp-{}-{}".format(serverNo,i)
            command = "ncloud vserver createBlockStorageInstance --profile \"{}\" --regionCode \"{}\" --serverInstanceNo \"{}\" --blockStorageName \"{}\" --blockStorageDiskDetailTypeCode SSD --blockStorageSize {}".format(profile, region, serverNo, name, volume[i])
            logging.info(command)

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                pass

    except Exception as e:
        exit(e)

def find_password(profile, region, serverNo, key, OS, USERPATH="."):
    """
    - Get Root/Administrator's Password of Instance and Create Login Info Log
    """
    try:
        limit = 0
        login = {
            "id":"",
            "password":""
        }
        
        if OS == "WND64":
            login["id"] = "Administrator"
        else:
            login["id"] = "root"

        # Check File
        key_path = USERPATH + "/" + key + ".pem"

        if not os.path.isfile(key_path):
            logging.error("File ERROR: \"{}\" File dose not exist".format(key_path))
            return login

        command = "ncloud vserver getRootPassword --profile \"{}\" --regionCode \"{}\" --serverInstanceNo \"{}\" --privateKey \"file://{}\"".format(profile, region, serverNo, key_path)
        logging.info(command)

        while (login["password"] == "") and (limit < 20):
            sleep(5)
            limit += 1
            logging.info("find_password limit : {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                login["password"] = json.loads(stdout)["getRootPasswordResponse"]["rootPassword"]

        return login

    except Exception as e:
        exit(e)


def describe_instance(profile, region, serverNo, vmname, USERPATH="."):
    """
    - Describe running Instance and Create Instance Info Log
    """
    try:
        limit = 0
        result = []

        # Get running Instance Information 
        command = "ncloud vserver getServerInstanceList --profile \"{}\" --regionCode \"{}\" --serverInstanceNoList \"{}\" --serverInstanceStatusCode RUN".format(profile, region, serverNo)
        logging.info(command)

        while (len(result) <= 0) and (limit < 50):
            sleep(60)
            limit += 1
            logging.info("describe_instance limit : {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                result = json.loads(stdout)["getServerInstanceListResponse"]["serverInstanceList"]

        # Create Instance Log
        info = {}
        if len(result) > 0:
            info = {}
            info["name"] = result[0]["serverName"]
            info["status"] = "success"
            info["publicip"] = result[0]["publicIp"]
            OS_ = result[0]["platformType"]["code"] # LNX64 or WND64
            info["login"] = find_password(profile, region, serverNo, result[0]["loginKeyName"], OS_, USERPATH)
        else:
            info["name"] = vmname
            info["status"] = "fail" 
        
        return info

    except Exception as e:
        exit(e)


def getServerNo(profile, region, vmname):
    try:
        server_info = {
            "serverNo":"",
            "serverName":"",
            "publicIpNo":"",
            "status":""
        }
        command = "ncloud vserver getServerInstanceList --profile \"{}\" --regionCode \"{}\" --serverName \"{}\" --sortedBy serverName".format(profile, region, vmname)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)["getServerInstanceListResponse"]["serverInstanceList"]
            logging.info(result)
            for i in range(len(result)):
                if vmname == result[i]["serverName"]:
                    server_info["serverNo"] = result[i]["serverInstanceNo"]
                    server_info["serverName"] = result[i]["serverName"]
                    server_info["publicIpNo"] = result[i]["publicIpInstanceNo"]
                    server_info["status"] = result[i]["serverInstanceStatusName"]
                    break

        logging.info(server_info)
        
        return server_info
            
    except Exception as e:
        exit(e)

def getBlockNo(profile, region, serverNo):
    try:
        blockNo_list = []
        command = "ncloud vserver getBlockStorageInstanceList --profile \"{}\" --regionCode \"{}\" --serverInstanceNo \"{}\" --blockStorageTypeCodeList SVRBS".format(profile, region, serverNo)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)["getBlockStorageInstanceListResponse"]["blockStorageInstanceList"]

            for i in range(len(result)):
                blockNo_list.append(result[i]["blockStorageInstanceNo"])

        return blockNo_list
    except Exception as e:
        exit(e)

def deleteBlock(profile, region, blockNo_list):
    try:
        result = ""
        limit = 0

        blockNos = ' '.join(op for op in blockNo_list)
        command = "ncloud vserver deleteBlockStorageInstances --profile \"{}\" --regionCode \"{}\" --blockStorageInstanceNoList \"{}\"".format(profile, region, blockNos)
        logging.info(command)

        while (limit < 60) and (result != "success"):
            limit += 1
            logging.info("deleteBlock limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
                result = "fail"
            else:
                logging.info(stdout)
                result = "success"
                break

        return result
    except Exception as e:
        exit(e)

def deletePublicIp(profile, region, pubIpNo):
    try:
        result = ""
        limit = 0

        command = "ncloud vserver deletePublicIpInstance --profile \"{}\" --regionCode \"{}\" --publicIpInstanceNo \"{}\"".format(profile, region, pubIpNo)
        logging.info(command)

        while (limit < 60) and (result != "success"):
            limit += 1
            logging.info("deletePublicIp limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
                result = "fail"
            else:
                logging.info(stdout)
                result = "success"
                break

        return result
    except Exception as e:
        exit(e)

def stopInstance(profile, region, serverNo):
    try:
        result = ""
        limit = 0

        command = "ncloud vserver stopServerInstances --profile \"{}\" --regionCode \"{}\" --serverInstanceNoList \"{}\"".format(profile, region, serverNo)
        logging.info(command)

        while (limit < 60) and (result != "success"):
            sleep(20)
            limit += 1
            logging.info("stopInstance limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
                result = "fail"
            else:
                logging.info(stdout)
                result = "success"
                break

        return result

    except Exception as e:
        exit(e)

def terminateInstance(profile, region, serverNo):
    try:
        result = ""
        limit = 0

        command = "ncloud vserver terminateServerInstances --profile \"{}\" --regionCode \"{}\" --serverInstanceNoList \"{}\"".format(profile, region, serverNo)    
        logging.info(command)

        while (limit < 60) and (result != "success"):
            sleep(20)
            limit += 1
            logging.info("terminateInstance limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
                result = "fail"
            else:
                logging.info(stdout)
                result = "success"
                break

        return result
    except Exception as e:
        exit(e)

