import os
import json
import threading
import platform
import subprocess
import sys
import logging

PLATFORM = platform.system() # Windows , Linux
lock = threading.Lock()


# Windows Disk image ID
DISK_IMAGE_DICT = {
    "windows-2012-r2":"windows-server-2012-r2-dc-v20220712",
    "windows-2016":"windows-server-2016-dc-v20220713",
    "windows-2019":"windows-server-2019-dc-v20220712",
    "windows-2022":"windows-server-2022-dc-v20220712"
} 

# STDOUT and STDERR to LOGGER
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

def user_login(authdata, USERPATH='.'):
    try:
        credentials_file = USERPATH+"/"+authdata["credentials_file"]
        if not os.path.isfile(credentials_file):
            exit("File ERROR: [{}] does not exist".format(credentials_file))
        
        with open(credentials_file, "r") as f:
            credentials = json.load(f)
        
        account = credentials["client_email"]
        project_id = credentials["project_id"]

        command = "gcloud auth activate-service-account \"{ACCOUNT}\" --key-file=\"{CREDENTIALS}\" --project=\"{PROJECT}\"" .format(ACCOUNT=account, CREDENTIALS=credentials_file, PROJECT=project_id)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            exit("stdout: {}, stderr: {}".format(stdout, stderr))
        else:
            return account, project_id
    
    except Exception as e:
        exit(e)

def create_disk(vm_name, img_project, img_family, volumes):
    """
        - standard persistent disk
        - min 10GB ~ max 64 TB
    """
    lock.acquire()
    disk_list = []

    for i in range(len(volumes)):
        disk = "--create-disk="
        disk += "auto-delete=yes,"
        dname = "{}-disk-{}".format(vm_name, str(i+1))
        disk += ("device-name={},".format(dname))
        disk += "name={},".format(dname)
        
        if (i == 0) and (img_project == "windows-cloud"):
            img = "projects/{}/global/images/{}".format(img_project, DISK_IMAGE_DICT[img_family])
            disk += "image={},".format(img)

        disk += "size={}".format(volumes[i])
        disk_list.append(disk)

    result = ' '.join(op for op in disk_list)
    lock.release()

    return result

def create_instance(account, project, region, vm_data, USERPATH='.'):
    try:
        command_list = []
        command_list.append("gcloud compute instances create --account=\"{ACCOUNT}\" \"{VMNAME}\"".format(ACCOUNT=account, VMNAME=vm_data["vm_name"]))
        command_list.append("--zone=\"{REGION}\"".format(REGION=region))
            
        if vm_data["OS"] and vm_data["OS_version"]:
            command_list.append("--image-project=\"{OS}\"".format(OS=vm_data["OS"]))
            command_list.append("--image-family=\"{OS_VERSION}\"".format(OS_VERSION=vm_data["OS_version"]))
        
        if vm_data["machine_type"]:
            command_list.append("--machine-type=\"{MACHINETYPE}\"".format(MACHINETYPE=vm_data["machine_type"]))

        if len(vm_data['volume']) > 0:
            disks = create_disk(vm_data["vm_name"], vm_data["OS"], vm_data["OS_version"], vm_data['volume'])
            command_list.append(disks)
        
        if vm_data["userdata"]:
            if vm_data["OS"] == "windows-cloud":
                scripts = "windows-startup-script-ps1=\"{PATH}/{USERDATA}\"".format(PATH=USERPATH,USERDATA=vm_data["userdata"])
            else:
                scripts = "startup-script=\"{PATH}/{USERDATA}\"".format(PATH=USERPATH,USERDATA=vm_data["userdata"])
            command_list.append("--metadata-from-file={}".format(scripts))
        
        if (vm_data["username"]) and (vm_data["ssh_authorized_keys"]):
            username = vm_data["username"]
            key_file = USERPATH + "/" + vm_data["ssh_authorized_keys"]

            with open(key_file, mode='r') as f:
                lines = f.readlines()
                key_value = lines[0]
            command_list.append("--metadata=ssh-keys=\"{USERNAME}:{KEY}\"".format(USERNAME=username, KEY=key_value))

        if vm_data["tags"]:
            command_list.append("--tags=\"{TAG}\"".format(TAG=vm_data["tags"]))
        
        command_list.append("--enable-display-device")
        command = ' '.join(op for op in command_list)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            result = "fail"
        else:
            logging.info(stdout)
            result = "success"

        return result
        
    except Exception as e:
        exit(e)

def check_firewallrule(account, tag):
    try:
        command = "gcloud compute firewall-rules list --account=\"{ACCOUNT}\" --filter=\"name:\"{FIREWALLNAME}\"\"".format(ACCOUNT=account, FIREWALLNAME=tag)
        if PLATFORM == "Windows":
            command += " --format=json(name,targetTags)"
        else:
            command += " --format=json\(name,targetTags\)"
        
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result =  json.loads(stdout)

            for i in range(len(result)):
                if ("targetTags" in result[i].keys()) and (tag in result[i]["targetTags"]):
                    return True
                else:
                    pass

        return False

    except Exception as e:
        exit(e)

def create_firewallrule(account, tag, portlist):
    try:
        command = "gcloud compute firewall-rules create --account=\"{ACCOUNT}\" \"{FIREWALLNAME}\" --allow=\"{PORTLIST}\" --target-tags=\"{TAG}\"".format(ACCOUNT=account, FIREWALLNAME=tag, PORTLIST=portlist, TAG=tag)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            logging.info(stdout)

    except Exception as e:
        exit(e)

def reset_windows_password(account, region, vmname, username):
    try:
        login = {
            "username":"",
            "password":""
        }

        command = "gcloud compute reset-windows-password --account=\"{ACCOUNT}\" \"{VMNAME}\" --zone=\"{REGION}\" --user=\"{USERNAME}\" --quiet --format=json".format(ACCOUNT=account, VMNAME=vmname, REGION=region, USERNAME=username)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
        else:
            result = json.loads(stdout)
            login["username"] = result["username"]
            login["password"] = result["password"]

        return login

    except Exception as e:
        exit(e)

def describe_instance(account, region, vm_data):
    try:
        limit = 0
        result = {}

        command = "gcloud compute instances describe --account=\"{ACCOUNT}\" \"{VMNAME}\" --zone=\"{REGION}\" --format=\"json(name,networkInterfaces[].accessConfigs[].natIP:label=EXTERNAL_IP)\"".format(ACCOUNT=account, VMNAME=vm_data["vm_name"], REGION=region)
        logging.info(command)

        while (limit < 20) and (result == {}):
            limit += 1
            logging.info("describe_instance limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            else:
                result = json.loads(stdout)

        if result != {}:
            result["status"] = "success"
            try:
                result['publicip'] = result["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
                del(result["networkInterfaces"])
            except:
                result['publicip'] = ""

            result["login"] = {}

            if vm_data["OS"] == "windows-cloud":
                logging.info("[ Reseting Windows password ]")
                login_info = reset_windows_password(account, region, vm_data["vm_name"], vm_data["username"])
                result["login"]["id"] = login_info["username"]
                result["login"]["password"] = login_info["password"]
            else:
                result["login"]["id"] = vm_data["username"]
        else:
            result["name"] = vm_data["vm_name"]
            result["status"] = "fail"

        return result
    except Exception as e:
        exit(e)

def delete_instance(account, project, region, vmname):
    """
    - When terminating Instance, automatically delete attached Disks and Public Ip  
    """
    try:
        command = "gcloud compute instances delete --account=\"{ACCOUNT}\" --project=\"{PROJECT}\" \"{VMNAME}\" --zone=\"{REGION}\" --quiet".format(ACCOUNT=account,PROJECT=project,VMNAME=vmname, REGION=region)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            result = "fail"
        else:
            result = "success"

        return result
    except Exception as e:
        exit(e)