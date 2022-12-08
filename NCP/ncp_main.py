import time
import argparse
from queue import Queue
from ncp_func import *

# add parameter
parser = argparse.ArgumentParser()
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
    profile = user_login(data["auth"])
    logging.info("[ Authorizing done ]")

    # Create VM
    logging.info("[ Creating VM start ]")
    region = data["auth"]["region"]
    serverNo = create_instance(profile, region, data["vm_info"])
    logging.info("[ Creating VM done ]")
    
    if serverNo is not None:
        logging.info("[ Getting VM information start ]")
        log['instance']  = describe_instance(profile, region, serverNo, data["vm_info"]["vm_name"], USERPATH)
        logging.info("[ Getting VM information done ]")
        
        # Attach Block volume
        logging.info("[ Attaching block volume start ]")
        attach_block(profile, region, serverNo, data["vm_info"]["volume"])
        logging.info("[ Attaching block volume done ]")
    else:
        log['instance'] = {}
        log['instance']["name"] = data["vm_info"]["vm_name"]
        log['instance']["status"] = "fail"

    Q.put(log)
    LOG_FILE = USERPATH +"/"+ data["vm_info"]["vm_name"] + "_create.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")
        
def terminating_worker(data): 
    log = {}
    log["instance"] = {}
    log["instance"]["name"] = data["vm_info"]["vm_name"]

    # Authorizing 
    logging.info("[ Authorizing start ]")
    region = data["auth"]["region"]
    profile = user_login(data["auth"])
    logging.info("[ Authorizing done ]")

    logging.info("[ Getting VM information start ]")
    result  = getServerNo(profile, region, data["vm_info"]["vm_name"])
    result["blockNo"] = getBlockNo(profile, region, result["serverNo"])
    logging.info("[ Getting VM information done ]")

    if result["serverNo"]:
        if result["status"] != "stopped" :
            logging.info("[ Stopping VM start ]")
            stop_result = stopInstance(profile, region, result["serverNo"])
            logging.info("[ Stopping VM done ]")
        
        if (result["status"] == "stopped") or (stop_result == "success"):
            if result["publicIpNo"]:
                logging.info("[ Deleting PublicIp ]")
                deletePublicIp(profile, region, result["publicIpNo"])

            if len(result["blockNo"]) > 0:
                logging.info("[ Deleting Block Storage ]")
                deleteBlock(profile, region, result["blockNo"])
            
            logging.info("[ Teminating VM start ]")
            log["instance"]["status"] = terminateInstance(profile, region, result["serverNo"])
            logging.info("[ Teminating VM done ]")
        else:
            log["instance"]["status"] = "fail"
    else:
        log["instance"]["status"] = "fail"

    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_delete.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent="\t")    

if __name__ == '__main__':
    logging.info("--------------------")
    logging.info("[{}] ----- Start ncp_main.py".format(time.strftime('%c')))
    
    threads = []
    thread_Q = Queue()
    threading.excepthook = excepthook
    
    data = load_json(info_json)["generate"]
    if data['cloud_platform'] == "ncp":
        if delete > 0 :
            t = threading.Thread(target=terminating_worker, args=([data]))
        else:
            t = threading.Thread(target=creating_worker, args=(data, thread_Q))
        t.start()
        threads.append(t)

        for thread in threads:
            thread.join()
    
    logging.info("----------------------------------")
    logging.info("[{}] ----- Finished ncp_main.py".format(time.strftime('%c')))   
    
    if delete == 0:
        logging.info("Summary information about VM:")
        for q in thread_Q.queue:
            logging.info(json.dumps(q, indent='\t'))
        