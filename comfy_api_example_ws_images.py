import websocket
import uuid
import json
import urllib.request
import urllib.parse
import random
import os
import sys
import requests

json_server_address = "192.168.191.182"#这个变量需要配置文件传入

comfyui_server_address = json_server_address + "/server/"

client_id = str(uuid.uuid4())#这个clientid需要计算出来


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

#暂时用不到
def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(comfyui_server_address, url_values)) as response:
        return response.read()

#暂时用不到
def get_history(prompt_id):
    try:
        with urllib.request.urlopen("http://{}/history/{}".format(comfyui_server_address, prompt_id)) as response:
            return json.loads(response.read())
    except urllib.error.URLError as e:
        print(e.reason)
        return None


def get_jsonapi(client_version):
    '''获取jsonapi文件\n
    client_version: 传入当前客户端的版本号,此版本号从客户端配置文件获取
    '''
    try:
        with urllib.request.urlopen("http://{}/getworkflowfile?version={}".format(json_server_address, client_version)) as response:
            return json.loads(response.read())
    except urllib.error.URLError as e:
        print(e.reason)
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


def modify_input_node(workflow_json, picture_name):
    '''为输入图片接口赋值--(只匹配一个)\n
    workflow_json: 传入从服务端获取的jsonapi的内容\n
    picture_name: 传入已经上传的图片名称\n
    return: 函数执行状态
    '''
    if not isinstance(workflow_json, dict):
        return False
    for key in workflow_json:
        value = workflow_json[key]
        if not any(value_img == "LoadImage" for value_img in value.values()):
            continue
        if not "inputs" in value:
            continue
        image_node_input = value["inputs"]
        if not "image" in image_node_input:
            continue
        value["inputs"]["image"] = picture_name
        return True
    return False


def modify_all_ksampler_seed(workflow_json):
    '''为k采样器随机种子赋值，不赋值的话每次生成图片都一样\n
    workflow_json: 传入从服务端获取的jsonapi的内容\n
    return: 函数执行状态
    '''
    if not isinstance(workflow_json, dict):
        return False
    for key in workflow_json:
        value = workflow_json[key]
        if not any(value_img == "KSampler" for value_img in value.values()):
            continue
        if not "inputs" in value:
            continue
        image_node_input = value["inputs"]
        if not "seed" in image_node_input:
            continue
        value["inputs"]["seed"] = random.randint(1, 922431687473039)
    return True


def search_node_by_classtype(workflow_json, node_classtype):
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


# ！！整体缺功能！！所有失败及异常需要有处理逻辑并记录日志，以便后续排查和用户侧提示
# ！！需要想清楚哪些错误可以继续运行，哪些错误不能继续，哪些错误需要重新运行，尝试几次后仍然失败需要退出程序
if __name__ == "__main__":
    picture_name = "123.png"

    # 第一步：获取jsonapi文件
    workflow_json = get_jsonapi("1.0")
    # ！！这里缺功能！！：把获取下来的jsonapi文件校验json数据是否损坏后，保存到本地，以便下次使用
    if workflow_json is None:
        print("获取jsonapi失败")
    # ！！这里缺功能！！：如果获取失败，程序正常执行，调用本地自带的那个jsonapi文件

    # 第二步：上传图片到服务器
    script_path = os.path.realpath(os.path.dirname(sys.argv[0]))
    image_path = script_path+'/' + picture_name
    status_upload_image = upload_image(image_path)

    # 第三步：修改jsonapi文件，给该赋值的参数赋值**注意版本兼容性**
    status_modify_input_node = modify_input_node(workflow_json, picture_name)
    status_modify_all_ksampler_seed = modify_all_ksampler_seed(workflow_json)
    # ！！这里缺功能！！：修改选择哪个大模型？要修改吗-不确定-需要问博涵
    # ！！这里缺功能！！：修改选择哪个lora风格模型
    # ！！这里缺功能！！：修改正向关键词,并根据相应配置文件添加激活选择的lora模型参数
    # ！！这里缺功能！！：修改负向关键词

    # 第四步：通过websocket接口发送jsonapi文件，获取图片
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(comfyui_server_address, client_id))
    output_node_num = search_node_by_classtype(
        workflow_json, "SaveImageWebsocket")
    images = get_images(ws, workflow_json, output_node_num)

    # 第五步：获取图片并显示
    for node_id in images:
        for image_data in images[node_id]:
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(image_data))
            image.show()
