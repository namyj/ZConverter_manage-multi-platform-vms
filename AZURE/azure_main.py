import time
import argparse
from queue import Queue
from azure_func import *

parser = argparse.ArgumentParser()

# add parameter
parser.add_argument('--info_json', dest="info_json")
parser.add_argument('--delete', '-d', dest="delete", action="count", default=0)

# parameter 
args = parser.parse_args()
info_json = args.info_json
delete = args.delete

if PLATFORM == "Windows":
    USERPATH = '/'.join(op for op in info_json.split('\\')[:-1])
else:
    USERPATH = '/'.join(op for op in info_json.split('/')[:-1])

sys_logger(
    level=logging.DEBUG,
    format="[%(levelname)-5.5s] %(message)s",
    filename="{}/running.log".format(USERPATH),
    filemode='a'
)

def creating_worker(data, Q):
    log = {}

    # Authorizing
    logging.info("[ Authorizing start ]")
    sub_id = user_login(data["auth"])
    region = data["auth"]["region"]
    logging.info("[ Authorizing done ]")
    
    # Create Resource Group
    logging.info("[ Creating RESOURCE GROUP start ]")
    rg_result = True
    RESOURCE_GROUP = create_resource_group(sub_id, region, data["vm_info"]["vm_name"])
    logging.info("[ Creating RESOURCE GROUP done ]")

    logging.info("[ Creating Public IP & NSG ]")
    if RESOURCE_GROUP["status"] == "success":
        PUB_IP = create_public_ip(sub_id, region, RESOURCE_GROUP["name"], data["vm_info"]["vm_name"])
        NSG = create_network_security_group(sub_id, region, RESOURCE_GROUP["name"], data["vm_info"]["vm_name"])
    else:
        rg_result = False

    logging.info("[ Creating VNET ]")
    if (rg_result) and (NSG["status"] == "success"):
        VNET = create_vnetwork(sub_id, region, RESOURCE_GROUP["name"], NSG["name"], data["vm_info"]["vm_name"])
    else:
        rg_result = False 

    logging.info("[ Creating VM start ]")
    if (rg_result):
        result = create_instance(sub_id, region, RESOURCE_GROUP["name"], VNET["name"], VNET["subnet"], PUB_IP["name"], NSG["name"], data["vm_info"], USERPATH)
    else:
        result = None
    logging.info("[ Creating VM done ]")

    if result is not None:
        # Execute userdata
        if data["vm_info"]["userdata"]:
            logging.info("[ Running Userdata ]")
            run_userdata(sub_id, RESOURCE_GROUP["name"], data["vm_info"]["vm_name"], data["vm_info"]["userdata"], USERPATH)
        
        logging.info("[ Getting VM information start ]")
        log["instance"] = describe_isntance(data["vm_info"], RESOURCE_GROUP["name"], result)
        logging.info("[ Getting VM information done ]")
    else:
        log['instance'] = {}
        log['instance']["name"] = data["vm_info"]["vm_name"]
        log['instance']["status"] = "fail"
        log['instance']["resource_group"] = RESOURCE_GROUP["name"]

    Q.put(log)
    LOG_FILE = USERPATH +"/"+ data["vm_info"]["vm_name"] + "_create.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")

def terminating_worker(data): 
    log = {}

    # Authorizing
    logging.info("[ Authorizing start ]")
    sub_id = user_login(data["auth"])
    logging.info("[ Authorizing done ]")
    
    log['instance'] = {}
    log['instance']["name"] = data["vm_info"]["vm_name"]
    
    # Delete Resource Group
    logging.info("[ Deleting Resource Group start ]")
    log['instance']["status"] = delete_resource_group(sub_id, data["vm_info"]["vm_name"])
    logging.info("[ Deleting Resource Group done ]")

    LOG_FILE = USERPATH +"/"+ data["vm_info"]["vm_name"] + "_delete.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")

if __name__ == '__main__':
    logging.info("--------------------")
    logging.info("[{}] ----- Start azure_main.py".format(time.strftime('%c')))   
    
    threads = []
    thread_Q = Queue()
    threading.excepthook = excepthook

    data = load_json(info_json)["generate"]
    if data['cloud_platform'] == "azure":
        if delete > 0 :
            t = threading.Thread(target=terminating_worker, args=(data,))
        else:
            t = threading.Thread(target=creating_worker, args=(data, thread_Q))
        t.start()
        threads.append(t)

        for thread in threads:
            thread.join()
    
    logging.info("----------------------------------")
    logging.info("[{}] ----- Finished azure_main.py".format(time.strftime('%c')))   
    
    if delete == 0:
        logging.info("Summary information about VM:")
        for q in thread_Q.queue:
            logging.info(json.dumps(q, indent='\t'))
        

