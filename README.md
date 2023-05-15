# Managing program for Multi platform VMs 

### 사용 방법
1. 클라우드 플랫폼 CLI 사용을 위해 인증키 준비한다.
  ex) aws - access key & private access key
2. 원하는 플랫폼 폴더의 ex_info.json을 변경한다.
3. VM을 생성한다.
  
    ex) AWS 인스턴스를 생성하는 경우
  
    ```
    aws_main.py --info_json ex_info.json
    ```
    
5. VM을 삭제한다.
  
    ex) AWS 인스턴스를 삭제하는 경우
  
    ```
    aws_main.py --info_json ex_info.json -d
    ```
    

### 지원하는 클라우드 플랫폼
- AWS
- AZURE
- GCP
- NCP
- OCI
