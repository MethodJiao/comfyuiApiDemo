import websocket
import uuid
import json
import urllib.request
import urllib.parse
import random
import os
import sys
import requests
from PIL import Image

timeout_num = 5

server_address = "192.168.191.182"  # 这个变量需要配置文件传入

comfyui_server_address = server_address + "/server/"

client_id = str(uuid.uuid4())  # 这个clientid需要计算出来

script_path = os.path.realpath(os.path.dirname(sys.argv[0]))


class StyleData:
    def __init__(self, style_dir):
        self.style_dir = style_dir
        self.thumbnail_dir = style_dir+'/thumbnail.png'
        self.route_dir = style_dir+'/route.json'
        self.workflow_dir = style_dir+'/workflow_api.json'
        with open(self.workflow_dir, 'r', encoding='utf-8') as f:
            self.workflow = json.load(f)
        with open(self.route_dir, 'r', encoding='utf-8') as f:
            self.route = json.load(f)
        with Image.open(self.thumbnail_dir) as image:
            self.thumbnail = image

    def getworkflow(self):
        return self.workflow

    def getroute(self):
        return self.route

    def getthumbnail(self):
        return self.thumbnail


def queue_prompt(workflow_json):
    '''发起排队请求\n
    workflow_json: 传入从服务端获取并修改后的jsonapi的内容
    '''
    try:
        p = {"prompt": workflow_json, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(
            "http://{}/prompt".format(comfyui_server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.URLError as e:
        print(e.reason)
        return None

# 暂时用不到


def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(comfyui_server_address, url_values)) as response:
        return response.read()

# 暂时用不到


def get_history(prompt_id):
    try:
        with urllib.request.urlopen("http://{}/history/{}".format(comfyui_server_address, prompt_id)) as response:
            return json.loads(response.read())
    except urllib.error.URLError as e:
        print(e.reason)
        return None



def load_local_style(version):
    '''加载本机配置\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    dataset = {}
    # with open(script_path+'/style_version.cfg', 'r') as file:
    #     local_version = file.readline()
        #装载本地配置
    with open(script_path+'/'+version+'/style_package_map.json', 'r', encoding='utf-8') as json_file:
        style_list= json.load(json_file)
        for key, value in style_list.items():
            if not "dir" in value:
                continue
            dir_name = value["dir"]
            dataset[key] = version+"/"+dir_name
        return dataset
    
def try_get_style(client_version):
    '''获取风格,路由文件,缩略图\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    dataset = {}
    local_version = None
    server_style_version = None
    try:
        # 比较本地版本和服务端版本
        with open(script_path+'/style_version.cfg', 'r') as file:
            # global local_version
            local_version = file.readline()
            response = requests.get(
                "http://{}/static/{}/style_version.cfg".format(server_address, client_version), timeout=timeout_num)
            # global server_style_version
            server_style_version = response.text
            if int(local_version) >= int(server_style_version):
                # 本地版本已经最新，装载本地配置
                dataset = load_local_style(local_version)
                return dataset
            
        # 本地非最新，获取风格包
        response = requests.get(
            "http://{}/static/{}/{}/style_package_map.json".format(server_address, client_version, server_style_version), timeout=timeout_num)
        style_list = json.loads(response.text)
        with open(script_path+'/'+server_style_version+'/style_package_map.json', 'w', encoding='utf-8') as json_file:
            json_file.write(response.text)
        for key, value in style_list.items():
            if not "dir" in value:
                continue
            dir_name = value["dir"]

            os.makedirs(script_path+'/' + '/' +
                        server_style_version + '/' + dir_name, exist_ok=True)
            # 保存工作流json
            response = requests.get(
                "http://{}/static/{}/{}/{}/workflow_api.json".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/workflow_api.json', 'w', encoding='utf-8') as json_file:
                json_file.write(response.text)
            # 保存图片png
            response = requests.get(
                "http://{}/static/{}/{}/{}/thumbnail.png".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/thumbnail.png', 'wb') as png_file:
                png_file.write(response.content)
            # 保存路由json
            response = requests.get(
                "http://{}/static/{}/{}/{}/route.json".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/route.json', 'w', encoding='utf-8') as png_file:
                png_file.write(response.text)
            dataset[key] = local_version+"/"+dir_name
        return dataset
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.Timeout):
            # 处理超时异常的逻辑
            print('请求超时')
            return None
        elif isinstance(e, requests.exceptions.ConnectionError):
            # 处理连接错误异常的逻辑
            print('连接错误')
            return None
        else:
            # 处理其他异常的逻辑
            print(str(e))
            return None


def get_ban_keyword(client_version):
    '''获取敏感词过滤库\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    try:
        response = requests.get(
            "http://{}/static/{}/ban_keyword.json".format(server_address, client_version), timeout=timeout_num)
        ban_word_list = json.loads(response.text)
        if not "dir" in ban_word_list:
            return None
        return ban_word_list["dir"]
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.Timeout):
            # 处理超时异常的逻辑
            print('请求超时')
            return None
        elif isinstance(e, requests.exceptions.ConnectionError):
            # 处理连接错误异常的逻辑
            print('连接错误')
            return None
        else:
            # 处理其他异常的逻辑
            print(str(e))
            return None

def get_images(ws, workflow_json, output_node_num):
    '''发起排队请求并且等待接收图片\n
    workflow_json: 传入从服务端获取并修改后的jsonapi的内容
    output_node_num: 传入输出节点的编号
    '''
    prompt_id = queue_prompt(workflow_json)['prompt_id']
    output_images = {}
    current_node = ""
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if not message['type'] == 'executing':
                continue
            data = message['data']
            if not data['prompt_id'] == prompt_id:
                continue
            if data['node'] is None:
                break  # 流程完毕了
            else:
                current_node = data['node']
        else:
            if not current_node == output_node_num:
                continue
            images_output = output_images.get(current_node, [])
            images_output.append(out[8:])
            output_images[current_node] = images_output

    return output_images


def upload_image(image_path):
    '''上传图片\n
    image_path: 图片绝对路径\n
    return: 函数执行状态
    '''
    try:
        file_name = os.path.basename(image_path)
        with open(image_path, 'rb') as img_file:
            img_content = img_file.read()
            files = {
                'image': (file_name, img_content),
                'Content-Type': 'multipart/form-data ',
            }
            response = requests.post(
                "http://{}/upload/image".format(comfyui_server_address), files=files)
            return response.status_code
    except requests.RequestException as e:
        print(e.reason)
        return None


def modify_node_byroute(style_data: StyleData, modify_info):
    '''为要改值的节点改值，依据路由文件\n
    style_data: style_data加载好的数据结构\n
    modify_info: 改值信息例如：{输入图片:16666.png},其中key部分必须存在于route.json内\n
    return: 函数执行状态
    '''
    map_route_dir = {}#搜索名称：路由路径
    map_route_modify = {}#搜索名称：改值字段
    route_data = style_data.getroute()
    for key in modify_info:
        if not key in route_data:
            continue
        route_info_node = route_data[key]
        if not "key" in route_info_node:
            continue
        if not "route" in route_info_node:
            continue
        searchname = route_info_node["key"]
        map_route_dir[searchname] = route_info_node["route"]
        map_route_modify[searchname] = modify_info[key]

    for key in style_data.getworkflow():
        value = style_data.getworkflow()[key]
        if not "_meta" in value:
            continue
        meta = value["_meta"]
        if not "title" in meta:
            continue
        if not meta["title"] in map_route_dir:
            continue
        search_name =meta["title"]
        route_value = map_route_dir[search_name]
        route_value_list = route_value.split(",")
        # 赋值目标字段
        for i in range(len(route_value_list)-1):
            value = value[route_value_list[i]]
        value[route_value_list[-1]] = map_route_modify[search_name]
    return True

def search_node_byroute(style_data: StyleData, node_name):
    '''为要改值的节点改值，依据路由文件\n
    style_data: style_data加载好的数据结构\n
    node_name: 节点名,是route.json内的key字段,必须存在于route.json内\n
    return: 节点对应字段值
    '''

    route_data = style_data.getroute()
    if not node_name in route_data:
        return None
    route_info_node = route_data[node_name]
    if not "key" in route_info_node:
        return None
    if not "route" in route_info_node:
        return None
    searchname = route_info_node["key"]
    # map_route_dir[searchname] = route_info_node["route"]
    # map_route_modify[searchname] = modify_info[key]

    for key in style_data.getworkflow():
        value = style_data.getworkflow()[key]
        if not "_meta" in value:
            continue
        meta = value["_meta"]
        if not "title" in meta:
            continue
        if not meta["title"] == searchname:
            continue
        route_value = route_info_node["route"]
        route_value_list = route_value.split(",")
        # 赋值目标字段
        for i in range(len(route_value_list)):
            value = value[route_value_list[i]]
        return value
    return None


def search_nodenumber_by_classtype(workflow_json, node_classtype):
    '''查找节点--(只匹配一个)\n
    workflow_json: 传入从服务端获取的jsonapi的内容\n
    node_classtype: 节点的classtype属性\n
    return: 节点编号， 如果没有找到则返回-1
    '''
    if not isinstance(workflow_json, dict):
        return -1
    for key in workflow_json:
        value = workflow_json[key]
        if not any(value_ws == node_classtype for value_ws in value.values()):
            continue
        return key
    return -1


def load_route_bystyle(style_string_dict):
    '''风格包装载\n
    style_string_dict: 风格路径列表\n
    return: 风格包数据结构
    '''
    style_data_dict = {}
    for style_name ,style_relative_dir in style_string_dict.items():
        style_dir = script_path+"/"+style_relative_dir
        if not os.path.exists(style_dir):
            continue
        style_data = StyleData(style_dir)
        # last_slash_index = style_relative_dir.rfind('/')
        # style_string = style_relative_dir[last_slash_index + 1:]
        style_data_dict[style_name] = style_data
    return style_data_dict


# ！！整体缺功能！！所有失败及异常需要有处理逻辑并记录日志，以便后续排查和用户侧提示
if __name__ == "__main__":
    # ！！这里缺功能！！：名字需要ramdom一下再叠加时间戳上传，否则同名文件服务端会用老的
    picture_name = "1666.png"

    # 第一步：获取风格包
    style_string_dict = try_get_style("1.0")
    if style_string_dict is None:
        print("本机版本匹配和联机拉取风格包均失败,不联网直接加载本机")
        with open(script_path+'/style_version.cfg', 'r') as file:
            local_version = file.readline()
            style_string_dict = load_local_style(local_version)

    style_data_dict = load_route_bystyle(style_string_dict)
    # ！！这里缺功能！！：加载缩略图到风格选择,style_data_dict里有全部所需用到的数据

    # 第二步：上传图片到服务器
    image_path = script_path+'/' + picture_name
    status_upload_image = upload_image(image_path)

    # ！！这里缺功能！！：选定风格后走第三步，这里假定选了古建风格
    # 第三步 选择风格后 修改工作流文件，给该赋值的参数赋值
    modify_info = {}
    modify_info["输入图片"] = picture_name
    modify_info["k采样种子"] = random.randint(1, 922431687473039)
    positive_keywords = search_node_byroute(style_data_dict["古建风格"], "正向关键词")
    Negative_keywords = search_node_byroute(style_data_dict["古建风格"], "反向关键词")
    modify_info["正向关键词"] = positive_keywords+""
    modify_info["反向关键词"] = Negative_keywords+""
    status = modify_node_byroute(style_data_dict["古建风格"],modify_info)

    # 第四步：通过websocket接口发送jsonapi文件，获取图片
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(comfyui_server_address, client_id))
    output_node_num = search_nodenumber_by_classtype(
        style_data_dict["古建风格"].getworkflow(), "SaveImageWebsocket")
    images = get_images(ws, style_data_dict["古建风格"].getworkflow(), output_node_num)

    # 第五步：获取图片并显示
    for node_id in images:
        for image_data in images[node_id]:
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(image_data))
            image.show()
