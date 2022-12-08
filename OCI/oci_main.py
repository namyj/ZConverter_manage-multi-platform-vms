import time
import argparse
from queue import Queue
from oci_func import * 

parser = argparse.ArgumentParser()

parser.add_argument('--info_json', dest="info_json") 
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
    config, profile = user_login(data["auth"], USERPATH)
    logging.info("[ Authorizing done ]")

    # Create VM
    logging.info("[ Creating VM start ]")
    result = create_instance(config, profile, data["vm_info"], data["auth"]["region"], data["auth"]["domain"], USERPATH)
    logging.info("[ Creating VM done ]")
    
    if result["iid"]: 
        # Attach block disk
        logging.info("[ Creating & Attaching Block volume start ]")
        for i in range(len(data["vm_info"]["volume"])):
            volume_name = data["vm_info"]["vm_name"]+"-"+str(i)
            vid = create_block_volume(config, profile, data["vm_info"]["compartment_id"], data["auth"]["region"], result["AD"], volume_name, int(data["vm_info"]["volume"][i]))
            if vid is not None:
                attach_block_volume(config, profile, result["iid"], vid)    
        logging.info("[ Creating & Attaching Block Block volume done ]")

        # Get information about instance
        logging.info("[ Getting VM information start ]")
        log["instance"] = describe_instance(config, profile, data["vm_info"]["OS"].lower(), data["auth"]["region"], result["AD"], data["vm_info"]["compartment_id"], result["iid"], data["vm_info"]["vm_name"])
        logging.info("[ Getting VM information done ]")   
    else:
        log["instance"] = {} 
        log["instance"]["name"] = data["vm_info"]["vm_name"]
        log["instance"]["status"] = "fail"

    Q.put(log)
    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_create.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent="\t")

    if result["shape-config-file"] and os.path.isfile(result["shape-config-file"]):
        os.remove(result["shape-config-file"])
        
def terminating_worker(data):
    log = {}
    
    # user login
    logging.info("[ Authorizing start ]")
    config, profile = user_login(data["auth"], USERPATH)
    logging.info("[ Authorizing done ]")

    # get instance id
    logging.info("[ Getting VM ID start ]")
    iid_list = get_instance_id(config, profile, data["vm_info"]["compartment_id"], data["auth"]["region"], data["auth"]["domain"], data["vm_info"]["vm_name"])
    logging.info("[ Getting VM ID done ]")

    log["instance"] = {}
    log["instance"]["name"] = data["vm_info"]["vm_name"]
    
    if iid_list is not None:
        for iid in iid_list:
            logging.info("[ Deleting Block volume start ]")

            volume_ids = get_block_volume_ids(config, profile, data["vm_info"]["compartment_id"], iid)

            for volume in volume_ids:
                detach_block_volume(config, profile, volume["volume-attachment-id"])
                delete_block_volume(config, profile, volume["volume-id"])

            logging.info("[ Deleting Block volume done ]")

            logging.info("[ Teminating VM start ]")
            log["instance"]["status"] = terminate_instance(config, profile, iid)
            logging.info("[ Teminating VM done ]")
    else:
        log["instance"]["status"] = "fail"

    LOG_FILE = USERPATH+"/"+data["vm_info"]["vm_name"]+"_delete.log"
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent="\t")    
        
if __name__ == '__main__':
    # pass config file waring
    os.environ['OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING'] = "True"
    logging.info("--------------------")
    logging.info("[{}] ----- Start oci_main.py".format(time.strftime('%c')))   
    
    threads = []
    thread_Q = Queue()
    threading.excepthook = excepthook
    
    data = load_json(info_json)["generate"]
    if data['cloud_platform'] == "oci":
        if delete > 0 :
            t = threading.Thread(target=terminating_worker, args=(data,))
        else:
            t = threading.Thread(target=creating_worker, args=(data, thread_Q))
        
        t.start()
        threads.append(t)

        for thread in threads:
            thread.join()

    logging.info("----------------------------------")

    if delete == 0:
        logging.info("Summary information about VM:")
        for q in thread_Q.queue:
            logging.info(json.dumps(q, indent='\t'))
