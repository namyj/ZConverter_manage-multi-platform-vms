import time
import argparse
from queue import Queue
from aws_func import *

parser = argparse.ArgumentParser()
lock = threading.Lock()

# parameter 
parser.add_argument('--info_json')
parser.add_argument('--delete', '-d', dest="delete", action="count", default=0)

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
    user_data = data['auth']
    profile, region = user_login(user_data)

    # Create VM
    logging.info("[ Creating VM start ]")
    result = create_instance(profile, region, data['vm_info'], USERPATH)
    OS_ = data['vm_info']['OS'].lower()
    logging.info("[ Creating VM done ]")

    if result["instance_id"] is not None:
        logging.info("[ Getting VM information start ]")
        log['instance'] = describe_instance(profile, region, data['vm_info']["vm_name"], result["instance_id"], OS_, USERPATH)
        logging.info("[ Getting VM information done ]")
    else:
        log['instance'] = {}
        log["instance"]["name"] = data['vm_info']["vm_name"]
        log['instance']["status"] = "fail"
        
        # delete Security Group list
        if result["sg_id"] is not None:
            delete_security_group(profile, result["sg_id"])

    Q.put(log)
    
    LOG_FILE = USERPATH+"/"+ data["vm_info"]["vm_name"] + "_create.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f,ensure_ascii=False, indent="\t")

    if (result["mapping_file"] is not None) and os.path.isfile(result["mapping_file"]):
        os.remove(result["mapping_file"])

def terminating_worker(data):
    log = {}
    
    logging.info("[ Authorizing start ]")
    user_data = data['auth']
    profile, region = user_login(user_data)
    logging.info("[ Authorizing done ]")

    logging.info("[ Getting VM ID start ]")
    instance_id_list = get_instance_ids(profile, region, data["vm_info"]["vm_name"])
    logging.info("[ Getting VM ID done ]")

    log["instance"] = {}
    log["instance"]["name"] = data["vm_info"]["vm_name"]
    
    if len(instance_id_list) > 0:
        logging.info("[ Teminating VM start ]")
        log["instance"]["status"] = delete_instance(profile, region, instance_id_list)
        logging.info("[ Teminating VM done ]")
    else:
        log["instance"]["status"] = "fail"
        
    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_delete.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent="\t")    


if __name__ == '__main__':
    logging.info("--------------------")
    logging.info("[{}] ----- Start aws_main.py".format(time.strftime('%c')))   

    threads = []
    thread_Q = Queue()
    threading.excepthook = excepthook

    data = load_json(info_json)["generate"]
    if data['cloud_platform'] == "aws":
        if delete > 0 :
            t = threading.Thread(target=terminating_worker, args=([data]))
        else:
            t = threading.Thread(target=creating_worker, args=(data, thread_Q))
        t.start()
        threads.append(t)

        for thread in threads:
            thread.join()

    logging.info("----------------------------------")
    logging.info("[{}] ----- Finished aws_main.py".format(time.strftime('%c')))       

    if delete == 0:
        logging.info("Summary information about VM:")
        for q in thread_Q.queue:
            logging.info(json.dumps(q, indent='\t'))
        