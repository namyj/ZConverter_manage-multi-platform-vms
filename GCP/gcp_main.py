import time
import argparse
from queue import Queue
from gcp_func import *

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

    logging.info("[ Authorizing start ]")
    account, project = user_login(data["auth"], USERPATH)
    logging.info("[ Authorizing done ]")

    logging.info("[ Creating VM start ]")
    result = create_instance(account, project, data["auth"]["region"], data["vm_info"], USERPATH)
    logging.info("[ Creating VM done ]")

    if result == "success":
        logging.info("[ Checking Firewall rule ]")
        fr_check = check_firewallrule(account, data["vm_info"]["tags"])

        if not fr_check:
            logging.info("[ Creating Firewall Rule start ]")
            create_firewallrule(account, data["vm_info"]["tags"], data["vm_info"]["firewall_rule"])
        else:
            logging.info("Firewall Rule Already exists")
    
        logging.info("[ Getting VM information start ]")
        log["instance"] = describe_instance(account, data["auth"]["region"], data["vm_info"])
        logging.info("[ Getting VM information done ]")
    else:
        log["instance"] = {}
        log["instance"]["name"] = data["vm_info"]["vm_name"]
        log["instance"]["status"] = "fail"

    Q.put(log)
    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_create.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")

def terminating_worker(data):
    log = {}
    
    logging.info("[ Authorizing start ]")
    account, project = user_login(data["auth"], USERPATH)
    logging.info("[ Authorizing done ]")

    logging.info("[ Deleting VM start ]")
    result = delete_instance(account, project, data["auth"]["region"], data["vm_info"]["vm_name"])
    logging.info("[ Deleting VM done ]")
    
    log["instance"] = {}
    log["instance"]["name"] = data["vm_info"]["vm_name"]
    log["instance"]["status"] = result
    
    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_delete.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")  

if __name__ == '__main__':
    logging.info("--------------------")
    logging.info("[{}] ----- Start gcp_main.py".format(time.strftime('%c'))) 
    
    threads = []
    thread_Q = Queue()
    threading.excepthook = excepthook
    
    data = load_json(info_json)["generate"]
    if data['cloud_platform'] == "gcp":
        if delete > 0 :
            t = threading.Thread(target=terminating_worker, args=(data,))
        else:
            t = threading.Thread(target=creating_worker, args=(data, thread_Q))
        t.start()
        threads.append(t)

        for thread in threads:
            thread.join()

    logging.info("----------------------------------")
    logging.info("[{}] ----- Finished gcp_main.py".format(time.strftime('%c')))  
    
    if delete == 0:
        logging.info("Summary information about VM:")
        for q in thread_Q.queue:
            logging.info(json.dumps(q, indent='\t'))