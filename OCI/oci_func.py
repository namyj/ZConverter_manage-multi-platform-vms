import os
import json
import re
import threading
import subprocess
import platform
import sys
import logging

lock = threading.Lock()
PLATFORM = platform.system()

# Ingress & Egress rules for Security List  
IN_RULE = [
  {
    "icmpOptions": {
      "code": 4,
      "type": 3
    },
    "isStateless": False,
    "protocol": "1",
    "source": "0.0.0.0/0"
  },
  {
    "icmpOptions": {
      "type": 3
    },
    "isStateless": False,
    "protocol": "1",
    "source": "10.0.0.0/16"
  },
  {
    "source": "***.***.***.***/32", # must change
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 22,
        "min": 22
      }
    }
  },
  {
    "source": "***.***.***.***/32", # must change
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 3389,
        "min": 3389
      }
    }
  },
  {
    "source": "***.***.***.***/32", # must change
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 3306,
        "min": 3306
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 9054,
        "min": 9051
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "17",
    "isStateless": True,
    "udpOptions": {
      "destinationPortRange": {
        "max": 9054,
        "min": 9051
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 50005,
        "min": 50000
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 80,
        "min": 80
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 53306,
        "min": 53306
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 139,
        "min": 139
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 445,
        "min": 443
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 111,
        "min": 111
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 2049,
        "min": 2049
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 4001,
        "min": 4001
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 5005,
        "min": 5000
      }
    }
  },
  {
    "source": "0.0.0.0/0",
    "protocol": "6",
    "isStateless": True,
    "tcpOptions": {
      "destinationPortRange": {
        "max": 3000,
        "min": 3000
      }
    }
  }
]

EG_RULE = [
    {
        "destination": "0.0.0.0/0",
        "protocol": "all",
        "isStateless": False
    }
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
    ex) run exit() in multi Thread
    """
    logging.error("exc_type:{},exc_value:{}".format(args.exc_type, args.exc_value))

def load_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def user_login(user_data, USERPATH="."):
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
        
        config_file_path = USERPATH+"/"+user_data["credentials_file"]
        with open(config_file_path, 'r') as fr:
            lines = fr.readlines()
            
            for line in lines:
                result = line.strip().rstrip('\n')
                # Read profile
                if (profile is None) and (re.match(r'^\[[a-zA-Z0-9]+\]',result)) and (re.sub(r"[^a-zA-Z0-9]", "", result).lower() == user_data["profile"].lower()):
                    profile = re.sub(r"[^a-zA-Z0-9]", "", result).lower()
                    new_file.append("[{}]\n".format(profile))
                
                # Read config file value
                elif (profile is not None) and (result != ""):
                    key, value = result.split("=")
                    if (key in list(config.keys())) and (config[key] is None):
                        if key == 'key_file':
                            value = USERPATH+"/"+user_data["configkey_file"] 
                        config[key] = value 
                        new_file.append("{}={}\n".format(key,value)) 
               
                if len(new_file) >= 6:
                    break
                
        if (profile is None) or (len(new_file) < 6):
            raise Exception("CONFIG FILE ERROR")
        
        # Save new config file
        with open(config_file_path, mode='w') as fw:
            fw.writelines(new_file)

        return config_file_path, profile

    except Exception as e:
        exit(e)

def create_vcn(config, profile, vm_name, compartment_id):
  try:
    vcn_name = "{}-vcn".format(vm_name)
    command = "oci network vcn create --config-file \"{CONFIG}\" --profile \"{PROFILE}\" -c \"{COMPARTMENT}\" --display-name \"{NAME}\" --cidr-blocks \'[\"10.0.0.0/16\"]\' --wait-for-state AVAILABLE ".format(CONFIG=config, PROFILE=profile, COMPARTMENT=compartment_id, NAME=vcn_name)
    command += "--query \"data.{\\\"vcn_id\\\":\\\"id\\\",\\\"default_route_table_id\\\":\\\"default-route-table-id\\\"}\""
    logging.info(command)

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    stdout, stderr = proc.communicate()

    if proc.returncode:
        raise Exception(stderr)
    else:
        result = json.loads(stdout)
        logging.info(result)
    
    return result

  except Exception as e:
    exit(e)

def create_internet_gateway(config, profile, compartment_id, vcn_id, rt_id):
    """
    - Limit for internet gateways per VCN : 1
    """
    try:
        ig_id = None
        command = "oci network internet-gateway create --config-file \"{CONFIG}\" --profile \"{PROFILE}\" -c \"{COMPARTMENT}\" --vcn-id \"{ID}\" --is-enabled true --is-enabled true --wait-for-state AVAILABLE".format(CONFIG=config, PROFILE=profile, COMPARTMENT=compartment_id, ID=vcn_id)
        command += " --query \"data.{\\\"id\\\":\\\"id\\\"}\""
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            ig_id = json.loads(stdout)["id"]
        
        # Update Route Table
        if ig_id is not None:
            route_rule = "[{\"cidrBlock\":\"0.0.0.0/0\",\"networkEntityId\":\""+ ig_id +"\"}]"
            command = "oci network route-table update --config-file \"{CONFIG}\" --profile \"{PROFILE}\" --rt-id \"{ID}\" --route-rules \'{RULE}\' --force --wait-for-state AVAILABLE".format(CONFIG=config, PROFILE=profile, ID=rt_id, RULE=route_rule)
            logging.info(command)

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error(stderr)
            else:
                logging.info(stdout)

    except Exception as e:
        exit(e)

def create_security_list(config, profile, vm_name, compartment_id, vcn_id, USERPATH="."):
  """
  - IN_RULE_FILEPATH: list of inbound rules
  - EG_RULE_FILEPATH: list of outbound rules
  """
  try:
    IN_RULE_FILEPATH = USERPATH + "/oci_in_rule.json"
    EG_RULE_FILEPATH = USERPATH + "/oci_eg_rule.json"
    lock.acquire()
    with open(IN_RULE_FILEPATH, "w") as fw:
      json.dump(IN_RULE, fw,ensure_ascii=False, indent="\t")

    with open(EG_RULE_FILEPATH, "w") as fw:
      json.dump(EG_RULE, fw,ensure_ascii=False, indent="\t")
    lock.release()

    securitylist_name = "{}-security-list".format(vm_name)
    command = "oci network security-list create --config-file \"{CONFIG}\" --profile \"{PROFILE}\" -c \"{COMPARTMENT}\" --display-name \"{NAME}\" --vcn-id \"{ID}\" --ingress-security-rules \"file://{INGRESS_FILE}\" --egress-security-rules \"file://{EGRESS_FILE}\" --wait-for-state AVAILABLE".format(CONFIG=config, PROFILE=profile, COMPARTMENT=compartment_id, NAME=securitylist_name, ID=vcn_id, INGRESS_FILE=IN_RULE_FILEPATH, EGRESS_FILE=EG_RULE_FILEPATH)
    command += " --query \"data.{id:id}\""
    logging.info(command)
    
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    stdout, stderr = proc.communicate()

    if proc.returncode:
        raise Exception(stderr)
    else:
        security_id = json.loads(stdout)["id"]
        
    return security_id
  except Exception as e:
    exit(e)

def create_subnet(config, profile, vm_name, compartment_id, vcn_id, security_id, rt_id):
    try:
        logging.info("[ Creating Subnet ]")
        subnet_name = "{}-subnet".format(vm_name)
        command = "oci network subnet create --config-file \"{}\" --profile \"{}\" --cidr-block \"10.0.0.0/24\" -c \"{}\" --vcn-id \"{}\" --display-name \"{}\" --route-table-id \"{}\" --security-list-ids \'[\"{}\"]\' --wait-for-state AVAILABLE".format(config, profile, compartment_id, vcn_id, subnet_name, rt_id, security_id)
        command += " --query \"data.{id:id}\""
        logging.info(command)
        
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            raise Exception(stderr)
        else:
            subnet_id = json.loads(stdout)["id"]

        return subnet_id
    
    except Exception as e:
        exit(e)

def find_imageid(config, profile, cid, region, OS, OS_version, shape):
    try:
        imageID = None
        command = "oci compute image list --config-file \"{}\" --profile \"{}\" -c \"{}\" --region \"{}\" --lifecycle-state AVAILABLE --operating-system \"{}\" --operating-system-version \"{}\" --shape \"{}\" --sort-by TIMECREATED --sort-order ASC --all".format(config, profile, cid, region, OS, OS_version, shape)
        command += " --query \"data[*].{\\\"base_image_id\\\":\\\"base-image-id\\\",\\\"id\\\":\\\"id\\\"}\""
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            try:
                result = json.loads(stdout)

                for i in range(len(result)):
                    if result[0]["base_image_id"] is not None:
                        imageID = result[0]["base_image_id"]
                        break
                    else:
                        imageID = result[0]["id"]
                        break
            except:
                logging.error("Image Id does not exist")

        logging.info("imageID: {}".format(imageID))
        return imageID

    except Exception as e:
        exit(e)


def create_instance(config, profile, vm_data, region, AD, USERPATH="."):
    instance_id = None
    command_list = []
    command_list.append("oci compute instance launch --config-file \"{}\" --profile \"{}\" --region \"{}\"".format(config, profile, region))
    command_list.append("--display-name \"{}\"".format(vm_data["vm_name"]))
    
    if vm_data["compartment_id"]:
        command_list.append("-c \"{}\" --availability-domain \"{}\"".format(vm_data["compartment_id"], AD))
    
    if vm_data["subnet_id"]:
        command_list.append("--subnet-id \"{}\"".format(vm_data["subnet_id"]))
    else:
        vcn_info = create_vcn(config, profile, vm_data["vm_name"], vm_data["compartment_id"])
        create_internet_gateway(config, profile, vm_data["compartment_id"], vcn_info["vcn_id"], vcn_info["default_route_table_id"])
        security_id = create_security_list(config, profile, vm_data["vm_name"], vm_data["compartment_id"], vcn_info["vcn_id"], USERPATH)
        subnet_id = create_subnet(config, profile, vm_data["vm_name"], vm_data["compartment_id"], vcn_info["vcn_id"], security_id, vcn_info["default_route_table_id"])
        command_list.append("--subnet-id \"{}\"".format(subnet_id))

    if vm_data["OS"] and vm_data["OS_version"]:
        imageID = find_imageid(config, profile, vm_data["compartment_id"], region, vm_data["OS"], vm_data["OS_version"], vm_data["machine_type"])
        
        if imageID is not None:
          command_list.append("--image-id \"{}\"".format(imageID))

    if vm_data["machine_type"] and vm_data["memory_size"] and vm_data["cpu_count"]:
        shape_config = {"memoryInGBs": int(vm_data["memory_size"]), "ocpus": int(vm_data["cpu_count"])}
        shape_config_file = USERPATH+"/"+vm_data["vm_name"]+vm_data["OS"]+"_shape_config.json"
        
        with open(shape_config_file, 'w') as f:
            json.dump(shape_config, f,ensure_ascii=False, indent="\t")
        
        command_list.append("--shape \"{}\"".format(vm_data["machine_type"])) 
        command_list.append("--shape-config \"file://{}\"".format(shape_config_file))
    
    if vm_data["loginkey"]:
        command_list.append("--ssh-authorized-keys-file \"{}/{}\"".format(USERPATH, vm_data["loginkey"]))

    if vm_data["userdata"]:
        command_list.append("--user-data-file \"{}/{}\"".format(USERPATH, vm_data["userdata"]))

    command_list.append("--assign-public-ip true --wait-for-state RUNNING")
    command = ' '.join(op for op in command_list)
    logging.info(command)

    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    stdout, stderr = proc.communicate()

    if proc.returncode:
        instance_id = None
        logging.error(stderr)
    else:
        result = json.loads(stdout)
        if 'data' in result.keys():
            instance_id = result['data']["id"]

    return {"iid":instance_id,"AD":AD,"shape-config-file":shape_config_file}


def create_block_volume(config, profile, cid, region, AD, volume_name, volume_size):    
    try:
        vid = None
        command = "oci bv volume create --config-file \"{}\" --profile \"{}\" --region \"{}\" -c \"{}\" --availability-domain \"{}\" --display-name \"{}\" --size-in-gbs {}".format(config, profile, region, cid, AD, volume_name, volume_size)
        command += " --wait-for-state AVAILABLE --query \"data.{id:id}\""
        logging.info(command)
    
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            result = json.loads(stdout)
            vid = result["id"]
        return vid
    except Exception as e:
        exit(e)

def attach_block_volume(config, profile, iid, vid):
    try:
        command = "oci compute volume-attachment attach --config-file \"{}\" --profile \"{}\" --type paravirtualized --instance-id \"{}\" --volume-id \"{}\" --wait-for-state ATTACHED".format(config, profile, iid, vid)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))

    except Exception as e:
        exit(e)

def describe_instance(config, profile, OS_, region, AD, cid, iid, vmname):
    try:
        log = {}
        limit = 0
        result = None

        command = "oci compute instance list-vnics --config-file \"{}\" --profile \"{}\" --region \"{}\" --availability-domain \"{}\" -c \"{}\" --instance-id \"{}\"".format(config, profile, region, AD, cid, iid)
        command += " --query \"data[0].{\\\"Name\\\":\\\"display-name\\\",\\\"PublicIP\\\":\\\"public-ip\\\",\\\"subnet_id\\\":\\\"subnet-id\\\"}\""
        logging.info(command)

        while (limit < 50) and (result is None):
            limit += 1
            logging.info("describe_instance limit --- {}".format(limit))

            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            stdout, stderr = proc.communicate()

            if proc.returncode:
                logging.error(stderr)
            else:
                logging.info(stdout)
                try:
                    result = json.loads(stdout)    
                except:
                    result = None
        
        if result is not None:
            log["name"] = result["Name"]
            log["status"] = "success"
            log["instance_id"] = iid
            log["subnet_id"] = result["subnet_id"]
            log["publicip"] = result["PublicIP"]
        
            if OS_ == "windows":
                log["login"] = get_windows_password(config, profile, iid)
            elif OS_ == "canonical ubuntu":
                log["login"] = {"id":"ubuntu"}
            else:
                log["login"] = {"id":"opc"}
        else:
            log["name"] = vmname
            log["status"] = "fail" 

        return log

    except Exception as e:
        exit(e)

def get_windows_password(config, profile, iid):
    try:
        login = None

        command = "oci compute instance get-windows-initial-creds --config-file \"{}\" --profile \"{}\" --instance-id \"{}\"".format(config, profile, iid)
        command += " --query \"data.{\\\"id\\\":\\\"username\\\", \\\"password\\\":\\\"password\\\"}\""
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            try:
                login = json.loads(stdout)
            except:
                login = None

        return login

    except Exception as e:
        exit(e)

def get_instance_id(config, profile, cid, region, AD, vmname):
    try:
        result = None
        command = "oci compute instance list --config-file \"{}\" --profile \"{}\" -c \"{}\" --region \"{}\" --availability-domain \"{}\" --display-name \"{}\" --lifecycle-state RUNNING --query \"data[*].id\"".format(config, profile, cid, region, AD, vmname)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            try:
                result = json.loads(stdout)
            except:
                result = None
                
        return result

    except Exception as e:
        exit(e)

def terminate_instance(config, profile, iid):
    try:
        command = "oci compute instance terminate --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" --force --wait-for-state TERMINATED".format(config, profile, iid)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
            return "fail"
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return "success"
            
    except Exception as e:
        exit(e)

def get_block_volume_ids(config, profile, cid, iid):
    try:
        volume_ids = []

        command = "oci compute volume-attachment list --config-file \"{}\" --profile \"{}\" -c \"{}\" --instance-id \"{}\"".format(config, profile, cid, iid)
        command += " --query \"data[*].{\\\"volume-attachment-id\\\":\\\"id\\\",\\\"volume-id\\\":\\\"volume-id\\\"}\" --raw-output"
        logging.info(command)
    
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            try:
                volume_ids= json.loads(stdout)
            except:
                volume_ids = []
        
        return volume_ids

    except Exception as e:
        exit(e)

def detach_block_volume(config, profile, volume_id):
    try:
        command = "oci compute volume-attachment detach --config-file \"{}\" --profile \"{}\" --volume-attachment-id \"{}\" --wait-for-state DETACHED --force".format(config, profile, volume_id)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
            return "fail"
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return "success"

    except Exception as e:
        exit(e)

def delete_block_volume(config, profile, volume_id):
    try:
        command = "oci bv volume delete --config-file \"{}\" --profile \"{}\" --volume-id \"{}\" --force".format(config, profile, volume_id)
        logging.info(command)

        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        stdout, stderr = proc.communicate()

        if proc.returncode:
            logging.error(stderr)
            return "fail"
        else:
            logging.info("\n [STDOUT] {}\n [STDERR] {}".format(stdout, stderr))
            return "success"

    except Exception as e:
        exit(e)
