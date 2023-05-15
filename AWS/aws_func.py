import os
import json
import threading
import subprocess
from time import sleep
import platform
import sys
import logging

PLATFORM = platform.system()
lock = threading.Lock()

IN_BOUND_PORTS = [
    {"protocol":"tcp","from":22,"to":22,"source":"218.145.116.162/32"},
    {"protocol":"tcp","from":3389,"to":3389,"source":"218.145.116.162/32"},
    {"protocol":"tcp","from":3306,"to":3306,"source":"218.145.116.162/32"},
    {"protocol":"tcp","from":80,"to":80,"source":"0.0.0.0/0"},   
    {"protocol":"tcp","from":111,"to":111,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":139,"to":139,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":443,"to":445,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":2049,"to":2049,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":3000,"to":3000,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":4001,"to":4001,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":5001,"to":5005,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":9051,"to":9054,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":50000,"to":50005,"source":"0.0.0.0/0"},
    {"protocol":"tcp","from":53306,"to":53306,"source":"0.0.0.0/0"},
    {"protocol":"icmp","from":-1,"to":-1,"source":"0.0.0.0/0"} # -1 == ALL
]

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

def delete_configure():
    """
    - delete .aws/config , .aws/credentials file
    """
    import platform
    PLATFORM = platform.system() # Windows , Linux

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

def user_login(user_data):
    try:   
        limit = 0
        login = False

        profile = user_data['profile']
        region = user_data["region"]

        while (not login) and (limit < 10):
            limit += 1
            logging.info("user_login limit --- {}".format(limit))

            lock.acquire()
            os.system("aws configure set aws_access_key_id \"{}\" --profile \"{}\"".format(user_data["access_key"], profile)) 
            os.system("aws configure set aws_secret_access_key \"{}\" --profile \"{}\"".format(user_data['secret_access_key'], profile)) 
            os.system("aws configure set region \"{}\" --profile \"{}\"".format(user_data['login_region'], profile)) 
            lock.release()

            login = check_login(profile)
               
        if login:
            logging.info("[ Authorizing success ]")
            return profile, region
        else:
            exit("[ Authorizing fail (limit exceed) ]")

    except Exception as e:
        exit(e)

def check_login(profile):
    try:
        command = "aws ec2 describe-instances --profile \"{}\"".format(profile)
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            if "Unable to parse config file: /root/.aws/credentials" in stderr:
                delete_configure()
            return False
        else:
            return True

    except Exception as e:
        exit(e)

def check_keypair(profile, key):
    try:
        command = "aws ec2 describe-key-pairs --profile \"{}\" --key-name \"{}\"".format(profile ,key)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return False
        else:
            return True

    except Exception as e:
        exit(e)

def create_mapping_json(volumes, vm_name, USERPATH="."):
    try:
        alpha = 98 # b~z
        filename = USERPATH+"/"+"mapping_{}.json".format(vm_name)

        mapping_json = []
        for i in range(len(volumes)):
            if alpha > 122:
                break 
                   
            disk_json = dict()
            disk_json["DeviceName"] = "/dev/sd{}".format(chr(alpha))
            disk_json["Ebs"] = {"DeleteOnTermination":True,"VolumeSize":volumes[i]}
            mapping_json.append(disk_json)
            alpha += 1
            
        lock.acquire()
        with open(filename, 'w') as f:
            json.dump(mapping_json, f,ensure_ascii=False, indent="\t")
        lock.release()
        
        return filename

    except Exception as e:
        exit(e)

def check_security_group(profile, sg_name):
    try:
        logging.info("[ Checking Security Group ]")

        command = "aws ec2 describe-security-groups --profile \"{}\" --group-names \"{}\"".format(profile, sg_name)
        command += " --query \"SecurityGroups[*].GroupId\""
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.warning(stderr)
            sg_id = None
        else:
            logging.info("\"{}\" already exists.".format(sg_name))
            results = json.loads(stdout)
            if len(results) > 0:
                sg_id = results[0]
        
        return sg_id

    except Exception as e:
        exit(e)

def create_security_group(profile, vm_name, sg_name):
    """
    - If do not specified VCP, Security Group will be created within default VPC
    - source : "***.***.***.***/32" , tcp : 22 / 3389 / 3306
    - source : "0.0.0.0/0" , tcp : 80 / 111 / 139 / 443-445 / 2049 / 3000 / 3306 / 9051-9054 / 50000-50005 / 53306 / 4001 / 5001, ICMP - all
    """
    try:
        logging.info("[ Creating Security Group ]")
        sg_id = None
        
        command = "aws ec2 create-security-group --profile \"{}\" --group-name \"{}\" --description \"security group for {}\"".format(profile, sg_name, vm_name)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            sg_id = json.loads(stdout)['GroupId']
            logging.info("sg_id: {}".format(sg_id))

        return sg_id

    except Exception as e:
        exit(e)

def add_security_group_rules(profile, sg_id):
    try:
        for i in range(len(IN_BOUND_PORTS)):
            command = "aws ec2 authorize-security-group-ingress --profile \"{}\" --group-id \"{}\" --ip-permissions".format(profile,sg_id)
            command += " IpProtocol={},FromPort={},ToPort={}".format(IN_BOUND_PORTS[i]["protocol"], IN_BOUND_PORTS[i]["from"], IN_BOUND_PORTS[i]["to"])
            command += ",IpRanges=[{CidrIp='" + IN_BOUND_PORTS[i]["source"] + "'}]"

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.warning(stderr)
            else:
                pass
    except Exception as e:
        exit(e)

def create_instance(profile, region, vm_data, USERPATH):
    try:
        filename = None 
        sg_id = None
        command_list = []
        command_list.append("aws ec2 run-instances --profile \"{}\" --region \"{}\"".format(profile, region))

        if vm_data['vm_name']:
            tag = 'Key=Name,Value={}'.format(vm_data['vm_name'])
            command_list.append('--tag-specifications "ResourceType=instance,Tags=[{'+tag+'}]"')

        if vm_data['image_id']:
            command_list.append("--image-id \"{}\"".format(vm_data['image_id']))

        if vm_data['machine_type']:
            command_list.append("--instance-type \"{}\"".format(vm_data['machine_type']))

        if vm_data['cpu_flexible']:
            command_list.append("--cpu-options \"CoreCount={},ThreadsPerCore=2\"".format(vm_data['cpu_count']))

        if vm_data['loginkey']:
            keypair = vm_data['loginkey']
            if check_keypair(profile, keypair):
                command_list.append("--key-name \"{}\"".format(keypair))

        if vm_data['security_group_id']:
            command_list.append("--security-group-ids \"{}\"".format(vm_data['security_group_id']))
        else:
            sg_name = "{}-group".format(vm_data['vm_name'])
            sg_id = check_security_group(profile, sg_name)

            if sg_id is None:
                sg_id = create_security_group(profile, vm_data['vm_name'], sg_name)
                
            add_security_group_rules(profile, sg_id)
            command_list.append("--security-group-ids {}".format(sg_id))

        if vm_data['volume']:
            filename = create_mapping_json(vm_data['volume'], vm_data['vm_name'], USERPATH)
            command_list.append("--block-device-mappings \"file://{}\"".format(filename))

        if vm_data['userdata']:
            command_list.append("--user-data \"file://{}/{}\"".format(USERPATH, vm_data['userdata']))

        command = ' '.join(op for op in command_list)
        logging.info(command)
    
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            iid = None
        else:
            result = json.loads(stdout)['Instances']
            iid = result[0]["InstanceId"]

        return {"instance_id":iid,"mapping_file":filename,"sg_id":sg_id}

    except Exception as e:
        exit(e)

def get_win_password(profile, instance_id, keypair, USERPATH="."):
    try:
        logging.info("[ Getting Windows Password ]")

        # If key file does not exist, return ""
        keypath = USERPATH + "/" + keypair + ".pem"
        if not os.path.isfile(keypath):
            logging.error("Keypair file does not exist")
            return ""
        
        # Get Windows Password
        pwd = ""
        limit = 0
        command = "aws ec2 get-password-data --profile \"{}\" --instance-id {} --priv-launch-key \"{}\"".format(profile, instance_id, keypath)
        logging.info(command)

        while pwd == "":
            sleep(10)
            limit += 1
            logging.info("find_win_password limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                pwd = json.loads(stdout)['PasswordData']
            
            if limit > 15:
                logging.error("get_win_password limit exceed")
                pwd = ""
            
        return pwd

    except Exception as e:
        exit(e)

def describe_instance(profile, region, vmname, iid, OS_, USERPATH="."):
    try:
        # Get Instance Info
        limit = 0
        result = None
        
        command_list = []
        command_list.append("aws ec2 describe-instances --profile \"{}\" --region \"{}\" --instance-ids \"{}\" --filter \"Name=instance-state-name,Values=running\"".format(profile, region, iid))
        command_list.append("--query \"Reservations[0].Instances[0].{instance_id:InstanceId,name:Tags[?Key==\'Name\']|[0].Value,publicip:PublicIpAddress,Key:KeyName}\" --output json")
        command = ' '.join(op for op in command_list)
        logging.info(command)

        while result is None:
            sleep(10)
            limit += 1
            logging.info("describe_instance limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                result = json.loads(stdout)
            
            if limit > 60:
                result = "fail"
        
        # Create Instance log
        if result == "fail": 
            result = {"name":vmname,"status":"fail"}
        else:
            result["status"] = "success"
            result["login"] = {}
            if OS_=="windows":
                result["login"]["id"] = "Administrator"
                result["login"]["password"] = get_win_password(profile, result["instance_id"], result["Key"], USERPATH)
            elif OS_=="centos":
                result["login"]["id"] = "centos"
            elif OS_=="ubuntu":
                result["login"]["id"] = "ubuntu"
            elif OS_=="rhel":
                result["login"]["id"] = "ec2-user"
            elif OS_=="debian":
                result["login"]["id"] = "admin"
            else:
                result["login"]["id"] = "ec2-user"
            
            # delete "Key" from result
            del result["Key"]

        return result

    except Exception as e:
        exit(e)

def delete_security_group(profile, sg_id):
    try:
        command = "aws ec2 delete-security-group --profile \"{}\" --group-id \"{}\"".format(profile, sg_id)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            pass
    
    except Exception as e:
        exit(e)

def get_instance_ids(profile, region, vmname):
    try:
        result = []
        command_list = []
        command_list.append("aws ec2 describe-instances --profile \"{}\" --region \"{}\" --filters Name=tag:Name,Values=\"{}\"".format(profile, region, vmname))
        command_list.append("Name=instance-state-name,Values=\"running\" --query \"Reservations[*].Instances[0].InstanceId\"")
        command = ' '.join(op for op in command_list)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)
            
        return result
        
    except Exception as e:
        exit(e)

def delete_instance(profile, region, iid_list):
    try:
        iids = ' '.join(id for id in iid_list)
        command = "aws ec2 terminate-instances --profile \"{}\" --region \"{}\" --instance-ids {}".format(profile, region, iids)
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