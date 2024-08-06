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
import logging
from datetime import datetime

timeout_num = 5

server_address = "192.168.191.182"  # 这个变量需要配置文件传入

comfyui_server_address = server_address + "/server/"

client_id = str(uuid.uuid4())  # 这个clientid需要计算出来

script_path = os.path.realpath(os.path.dirname(sys.argv[0]))

logger = None

# 风格包数据类


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
        response = urllib.request.urlopen(req)
        if response.status == 200:
            return json.loads(response.read())
        else:
            logger.error("queue_prompt状态错误: %s", response.status)
            return None
    except Exception as e:
        logger.error("queue_prompt发生错误: %s", e)
        return None


def get_image(filename, subfolder, folder_type):
    '''暂时用不到，根据路径获取图片\n
    '''
    try:
        data = {"filename": filename,
                "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(comfyui_server_address, url_values)) as response:
            return response.read()
    except Exception as e:
        logger.error("load_local_style发生错误: %s", e)
        return None


def get_history(prompt_id):
    '''暂时用不到，查询历史信息\n
    '''
    try:
        with urllib.request.urlopen("http://{}/history/{}".format(comfyui_server_address, prompt_id)) as response:
            return json.loads(response.read())
    except Exception as e:
        logger.error("load_local_style发生错误: %s", e)
        return None


def load_local_style(version):
    '''加载本机配置\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    try:
        dataset = {}
        # 装载本地配置
        with open(script_path+'/'+version+'/style_package_map.json', 'r', encoding='utf-8') as json_file:
            style_list = json.load(json_file)
            for key, value in style_list.items():
                if not "dir" in value:
                    continue
                dir_name = value["dir"]
                dataset[key] = version+"/"+dir_name
            return dataset
    except Exception as e:
        logger.error("load_local_style发生错误: %s", e)


def try_get_style(client_version):
    '''获取风格,路由文件,缩略图\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    dataset = {}
    local_version = None
    server_style_version = None
    try:
        # 比较本地版本和服务端版本，本地是最新就用本地
        with open(script_path+'/style_version.cfg', 'r') as file:
            local_version = file.readline()
            response = requests.get(
                "http://{}/static/{}/style_version.cfg".format(server_address, client_version), timeout=timeout_num)
            server_style_version = response.text
            if int(local_version) >= int(server_style_version):
                logger.info("联网比对版本，本地版本为最新，装载本地配置")
                dataset = load_local_style(local_version)
                if dataset:
                    logger.info("装载本地配置成功")
                return dataset

        logger.info("本地版本非最新，从服务端获取风格包")
        os.makedirs(script_path + '/' + server_style_version, exist_ok=True)
        response = requests.get(
            "http://{}/static/{}/{}/style_package_map.json".format(server_address, client_version, server_style_version), timeout=timeout_num)
        style_list = json.loads(response.text)
        with open(script_path+'/'+server_style_version+'/style_package_map.json', 'w', encoding='utf-8') as json_file:
            json_file.write(response.text)
        logger.info("保存风格映射文件style_package_map")
        for key, value in style_list.items():
            if not "dir" in value:
                continue
            dir_name = value["dir"]

            os.makedirs(script_path+'/' +
                        server_style_version + '/' + dir_name, exist_ok=True)
            # 保存工作流json
            response = requests.get(
                "http://{}/static/{}/{}/{}/workflow_api.json".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/workflow_api.json', 'w', encoding='utf-8') as json_file:
                json_file.write(response.text)
            logger.info("保存工作流json")
            # 保存图片png
            response = requests.get(
                "http://{}/static/{}/{}/{}/thumbnail.png".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/thumbnail.png', 'wb') as png_file:
                png_file.write(response.content)
            logger.info("保存图片png")
            # 保存路由json
            response = requests.get(
                "http://{}/static/{}/{}/{}/route.json".format(server_address, client_version, server_style_version, dir_name), timeout=timeout_num)
            with open(script_path+'/'+server_style_version+'/'+dir_name+'/route.json', 'w', encoding='utf-8') as png_file:
                png_file.write(response.text)
            logger.info("保存路由json")
            dataset[key] = server_style_version+"/"+dir_name

        logger.info("联网风格包更新无异常，保存版本号至本地")
        with open(script_path+'/style_version.cfg', 'w') as file:
            file.write(server_style_version)
        return dataset
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.Timeout):
            # 处理超时异常的逻辑
            logger.error("try_get_style请求超时")
            return None
        elif isinstance(e, requests.exceptions.ConnectionError):
            # 处理连接错误异常的逻辑
            logger.error("try_get_style连接错误")
            return None
        else:
            # 处理其他异常的逻辑
            logger.error('try_get_style'+str(e))
            return None


def get_ban_keyword(client_version):
    '''联网获取敏感词过滤库\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    try:
        response = requests.get(
            "http://{}/static/{}/ban_keyword.json".format(server_address, client_version), timeout=timeout_num)
        ban_word_list = json.loads(response.text)
        if not "ban" in ban_word_list:
            return None
        logger.info("装载敏感词库成功")
        return ban_word_list["ban"]
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.Timeout):
            # 处理超时异常的逻辑
            logger.error("get_ban_keyword请求超时")
            return None
        elif isinstance(e, requests.exceptions.ConnectionError):
            # 处理连接错误异常的逻辑
            logger.error("get_ban_keyword连接错误")
            return None
        else:
            # 处理其他异常的逻辑
            logger.error('get_ban_keyword'+str(e))
            return None


def upload_queue_and_get_images(ws, workflow_json, output_node_num):
    '''发起排队请求并且等待接收图片\n
    workflow_json: 传入从服务端获取并修改后的jsonapi的内容
    output_node_num: 传入输出节点的编号
    '''
    try:
        prompt_id = queue_prompt(workflow_json)['prompt_id']
        logger.info("上传排队成功，prompt_id: %s", prompt_id)
        output_images = {}
        current_node = ""
        while True:
            out = ws.recv()
            # logger.info(out)
            if isinstance(out, str):
                message = json.loads(out)
                if not message['type'] == 'executing':
                    continue
                data = message['data']
                if not data['prompt_id'] == prompt_id:
                    continue
                if data['node'] is None:
                    logger.info("运算流程完毕")
                    break  # 流程完毕了
                else:
                    current_node = data['node']
            else:
                if not current_node == output_node_num:
                    continue
                images_output = output_images.get(current_node, [])
                images_output.append(out[8:])
                output_images[current_node] = images_output
        if not output_images:
            logger.info("获取图片失败")
        else:
            logger.info("获取图片成功")
        return output_images
    except Exception as e:
        logger.error("upload_queue_and_get_images发生错误: %s", e)


def upload_image(image_path):
    '''上传图片\n
    image_path: 图片绝对路径\n
    return: 图片guid
    '''
    try:
        current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        file_name, file_extension = os.path.splitext(image_path)
        guidforimg = client_id +'_'+current_time + file_extension
        # file_name = os.path.basename(image_path)
        with open(image_path, 'rb') as img_file:
            img_content = img_file.read()
            files = {
                'image': (guidforimg, img_content),
                'Content-Type': 'multipart/form-data ',
            }
            response = requests.post(
                "http://{}/upload/image".format(comfyui_server_address), files=files)
            if response.status_code == 200:
                logger.info("上传图片成功")
                return guidforimg
            return None
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.Timeout):
            # 处理超时异常的逻辑
            logger.error("upload_image请求超时")
            return None
        elif isinstance(e, requests.exceptions.ConnectionError):
            # 处理连接错误异常的逻辑
            logger.error("upload_image连接错误")
            return None
        else:
            # 处理其他异常的逻辑
            logger.error('upload_image'+str(e))
            return None


def modify_node_byroute(style_data: StyleData, modify_info):
    '''为要改值的节点改值，依据路由文件\n
    style_data: style_data加载好的数据结构\n
    modify_info: 改值信息例如：{输入图片:16666.png},其中key部分必须存在于route.json内\n
    return: 函数执行状态
    '''
    try:
        map_route_dir = {}  # 搜索名称：路由路径
        map_route_modify = {}  # 搜索名称：改值字段
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
            search_name = meta["title"]
            route_value = map_route_dir[search_name]
            route_value_list = route_value.split(",")
            # 赋值目标字段
            for i in range(len(route_value_list)-1):
                value = value[route_value_list[i]]
            value[route_value_list[-1]] = map_route_modify[search_name]
        logger.info("应用工作流参数修改成功")
        return True
    except Exception as e:
        logger.error("modify_node_byroute发生错误: %s", e)


def search_node_byroute(style_data: StyleData, node_name):
    '''为要改值的节点改值，依据路由文件\n
    style_data: style_data加载好的数据结构\n
    node_name: 节点名,是route.json内的key字段,必须存在于route.json内\n
    return: 节点对应字段值
    '''
    try:
        route_data = style_data.getroute()
        if not node_name in route_data:
            return None
        route_info_node = route_data[node_name]
        if not "key" in route_info_node:
            return None
        if not "route" in route_info_node:
            return None
        searchname = route_info_node["key"]

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
    except Exception as e:
        logger.error("search_node_byroute发生错误: %s", e)


def search_nodenumber_by_classtype(workflow_json, node_classtype):
    '''查找节点--(只匹配一个)\n
    workflow_json: 传入从服务端获取的jsonapi的内容\n
    node_classtype: 节点的classtype属性\n
    return: 节点编号， 如果没有找到则返回-1
    '''
    try:
        if not isinstance(workflow_json, dict):
            return -1
        for key in workflow_json:
            value = workflow_json[key]
            if not any(value_ws == node_classtype for value_ws in value.values()):
                continue
            logger.info("定位输出节点成功")
            return key
        return -1
    except Exception as e:
        logger.error("search_nodenumber_by_classtype发生错误: %s", e)


def load_route_bystyle(style_string_dict):
    '''风格包装载\n
    style_string_dict: 风格路径列表\n
    return: 风格包数据结构
    '''
    try:
        style_data_dict = {}
        for style_name, style_relative_dir in style_string_dict.items():
            style_dir = script_path+"/"+style_relative_dir
            if not os.path.exists(style_dir):
                continue
            style_data = StyleData(style_dir)
            style_data_dict[style_name] = style_data
        return style_data_dict
    except Exception as e:
        logger.error("load_route_bystyle发生错误: %s", e)


def init_logger():
    '''初始化日志模块\n
    '''
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    os.makedirs(script_path + '/log', exist_ok=True)

    global logger
    logger = logging.getLogger('runtime')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(
        script_path+'/log/'+current_time+'.log', encoding="utf-8")
    ch = logging.StreamHandler()
    fh.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)


def try_ws_get_image(style_data_by_choose):
    try:
        ws = websocket.WebSocket()
        ws.connect(
            "ws://{}/ws?clientId={}".format(comfyui_server_address, client_id))
        logger.info("建立websocket成功")
        output_node_num = search_nodenumber_by_classtype(
            style_data_by_choose.getworkflow(), "SaveImageWebsocket")
        images = upload_queue_and_get_images(
            ws, style_data_by_choose.getworkflow(), output_node_num)
        return images
    except Exception as e:
        logger.error("try_ws_get_image发生错误: %s", e)


# ！！整体缺功能！！所有失败及异常需要有处理逻辑并记录日志，以便后续排查和用户侧提示（目前日志埋点过少，不全。在try_get_style函数内演示了一个日志完整示例）
# ！！整体缺功能！！超时机制，重试机制？
if __name__ == "__main__":
    try:
        # 初始化日志模块
        init_logger()
        logger.info("开始运行")

        picture_name = "1666.png"

        # 第一步：获取风格包
        style_string_dict = try_get_style("1.0")
        if style_string_dict is None:
            logger.warning("本机版本匹配和联机拉取风格包均失败,不联网直接加载本机")
            with open(script_path+'/style_version.cfg', 'r') as file:
                local_version = file.readline()
                style_string_dict = load_local_style(local_version)

        style_data_dict = load_route_bystyle(style_string_dict)
        # ！！这里缺功能！！：加载缩略图到风格选择UI,style_data_dict里有全部所需用到的数据

        # 第二步：上传图片到服务器
        image_path = script_path+'/' + picture_name
        guid_img = upload_image(image_path)

        # ！！这里缺功能！！：选定风格后走第三步，这里假定选了别墅风格
        style_name = "别墅风格"
        style_data_by_choose = style_data_dict[style_name]
        # 第三步 选择风格后 修改工作流文件，给该赋值的参数赋值
        modify_info = {}
        modify_info["输入图片"] = guid_img #这里一定要赋值upload_image返回来的guid_img
        modify_info["k采样种子"] = random.randint(1, 922431687473039)
        positive_keywords = search_node_byroute(style_data_by_choose, "正向关键词")
        Negative_keywords = search_node_byroute(style_data_by_choose, "反向关键词")
        modify_info["正向关键词"] = positive_keywords+""  # ！！这里缺功能！！：由界面赋值增加正向关键词
        modify_info["反向关键词"] = Negative_keywords+""  # ！！这里缺功能！！：由界面赋值增加反向关键词
        # ！！这里缺功能！！：清洗敏感词，需要反馈到ui上
        word = get_ban_keyword("1.0")

        # 应用修改
        status = modify_node_byroute(style_data_by_choose, modify_info)

        # 第四步：通过websocket接口发送jsonapi文件，获取图片

        images = try_ws_get_image(style_data_by_choose)

        # 第五步：获取图片并显示
        for node_id in images:
            for image_data in images[node_id]:
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(image_data))
                image.show()
    except Exception as e:
        logger.error("外层异常捕获： %s", e)
