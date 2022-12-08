"""
인스턴스 삭제 시 VCN/SUBNET 삭제 코드
- 라우트 테이블 내 인터넷 게이트웨이 cli로 제거 불가능 -> internet gateway 제거 후 삭제
- default 라우트 테이블, security list는 제거 불가능 -> default 인 경우 삭제 하지 X
"""
import os
import json


def getVcnInfo(config, profile, region, AD, compartment_id, instance_id):
    try:
        # get Subnet ID from Instance
        command = "oci compute instance list-vnics --config-file \"{}\" --profile \"{}\" --region \"{}\" --availability-domain \"{}\" -c \"{}\" --instance-id \"{}\" ".format(config, profile, region, AD, compartment_id, instance_id)
        command += "--query \"data[*].\\\"subnet-id\\\"\""
        subnet_ids = json.loads(os.popen(command).read())

        # get Another Network Resource Info
        results = []
        for id in subnet_ids:
            command = "oci network subnet get --config-file \"{}\" --profile \"{}\" --subnet-id \"{}\" ".format(config, profile, id)
            command += "--query \"data.{\\\"subnet_id\\\":\\\"id\\\",\\\"route_table_id\\\":\\\"route-table-id\\\",\\\"security_list_ids\\\":\\\"security-list-ids\\\",\\\"vcn_id\\\":\\\"vcn-id\\\"}\""
            subnet = json.loads(os.popen(command).read())

            # get VCN's Default route table ID and security list ID (default rt table, security list can not be deleted) 
            command = "oci network vcn get --config-file \"{}\" --profile \"{}\" --vcn-id \"{}\" ".format(config, profile, subnet["vcn_id"])
            command += "--query \"data.{\\\"default-route-table-id\\\":\\\"default-route-table-id\\\",\\\"default-security-list-id\\\":\\\"default-security-list-id\\\"}\""
            default_ids = json.loads(os.popen(command).read())

            subnet["default_route_table_id"] = default_ids["default-route-table-id"]
            subnet["default_security_list_id"] = default_ids["default-security-list-id"]
            results.append(subnet)

        return results
        
    except Exception as e:
        exit("error: {}".format(e))  

def teminate_instance(config, profile, iid):
    command = "oci compute instance terminate --config-file \"{}\" --profile \"{}\" --instance-id \"{}\" --force --wait-for-state TERMINATED 2>&1".format(config, profile, iid)
    print(command)

    result = os.popen(command).read()

    if "Action completed" in result:
        return "success"
    else:
        return "fail"

def deleteSubnet(config, profile,subnet_id):
    try:
        command = "oci network subnet delete --config-file \"{}\" --profile \"{}\" --subnet-id \"{}\" --force".format(config, profile, subnet_id)
        print(command)

        if os.system(command) == 0:
            return "success"
        else:
            return "fail"
    except Exception as e:
        exit("error: {}".format())

def deleteRouteTable(config, profile, rt_id):
    try:
        command = "oci network route-table delete --config-file \"{}\" --profile \"{}\" --rt-id \"{}\" --force".format(config, profile, rt_id) 
        print(command)

        if os.system(command) == 0:
            return "success"
        else:
            return "fail"
    except Exception as e:
        exit("error: {}".format())

def deleteSecurityList(config, profile, sl_id):
    try:
        command = "oci network security-list delete --config-file \"{}\" --profile \"{}\" --security-list-id \"{}\" --force".format(config, profile, sl_id)
        print(command)
        
        if os.system(command) == 0:
            return "success"
        else:
            return "fail"

    except Exception as e:
        exit("error: {}".format()) 

def deleteInternetGateway(config, profile, compartment_id, rt_id, vcn_id):
    try:
        # update Route table
        command = "oci network route-table update --config-file \"{}\" --profile \"{}\" --rt-id \"{}\" --route-rules \"[]\" --force".format(config, profile, rt_id)  # o
        print(command)
        result = json.loads(os.popen(command).read())

        # get Internet Gateway ID
        command = "oci network internet-gateway list --config-file \"{}\" --profile \"{}\" -c \"{}\" --vcn-id \"{}\" --query \"data[*].id\"".format(config, profile, compartment_id, vcn_id)
        print(command)
        ig_ids = json.loads(os.popen(command).read())

        for id in ig_ids:
            command = "oci network internet-gateway delete --config-file \"{}\" --profile \"{}\" --ig-id \"{}\" --force".format(config, profile, id)
            print(command)
            if os.system(command) == 0:
                return "success"
            else:
                return "fail"
    except Exception as e:
        exit("error: {}".format())   

def deleteVcn(config, profile, vcn_id):
    try:
        command = "oci network vcn delete --config-file \"{}\" --profile \"{}\" --vcn-id \"{}\" --force".format(config, profile, vcn_id)
        print(command)
        if os.system(command) == 0:
            return "success"
        else:
            return "fail"
    except Exception as e:
        exit("error: {}".format())     


os.environ['OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING'] = "True"

config = "/ZCM/back/router/VMProgram/OCI/1665991748421__oci_config"
profile = "default" 
region = "ap-seoul-1"
AD = "vgdH:AP-SEOUL-1-AD-1" 
compartment_id = "입력" 
instance_id = "입력"

# # 1. 네트워크 리소스 정보 추출
vcn_info = getVcnInfo(config, profile, region, AD, compartment_id, instance_id)
print(vcn_info)

# # 2. 인스턴스 삭제
# result = teminate_instance(config, profile, instance_id)
teminate_instance(config, profile, instance_id)
result = "success"

# 3. 네트워크 리소스 삭제
if result == "success":
    for i in range(len(vcn_info)):
        deleteSubnet(config, profile, vcn_info[i]["subnet_id"]) # o
  
        deleteInternetGateway(config, profile, compartment_id, vcn_info[i]["route_table_id"], vcn_info[i]["vcn_id"])
  
        if vcn_info[i]["route_table_id"] != vcn_info[i]["default_route_table_id"] :
            deleteRouteTable(config, profile, vcn_info[i]["route_table_id"]) 
  
        for sl_id in vcn_info[i]["security_list_ids"]:
            if sl_id != vcn_info[i]["default_security_list_id"]:
                deleteSecurityList(config, profile, sl_id)

        deleteVcn(config, profile, vcn_info[i]["vcn_id"]) 
else:
    pass
