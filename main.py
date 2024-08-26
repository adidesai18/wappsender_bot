from flask import Flask, request, jsonify
import requests
import os
import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
import json
from threading import Thread
import time
import logging

load_dotenv()

wappsender = os.getenv('wappsender')
bot_token = os.getenv('bot_token')
telegram_api_url = f"https://api.telegram.org/bot{bot_token}"
instance = os.getenv('instance')
wapp_token = os.getenv('wapp_token')
private_key=os.getenv('private_key')
private_key_id=os.getenv('private_key_id')
client_email=os.getenv('client_email')
project_id=os.getenv('project_id')
client_id=os.getenv('client_id')
client_x509_cert_url=os.getenv('client_x509_cert_url')

cred_dict = {
  "type": "service_account",
  "project_id": project_id,
  "private_key_id": private_key_id,
  "private_key": private_key,
  "client_email": client_email,
  "client_id": client_id,
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": client_x509_cert_url,
  "universe_domain": "googleapis.com"
}

cred = credentials.Certificate('wappsender-key.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

class WappSenderError(Exception):
    pass

login_op={
    'login_mode':False,
    'login_users':{
    }
}

exclude_op={
    'exclude_mode':False,
    'exclude_users':[]
}

upload_content_op={
    'upload_content_mode':False,
    'content':{
        'photos':[],
        'videos':[],
        'documents':[],
        'text':None
    }
}

broadcast_op={
    'broadcast_mode':False,
    'main_loop_mood':False,
    'group_count':0,
    'groups_len':0,
    'terminate':False
}

bot_commands_list=['/start','/login','/upload_content','/clear_content','/broadcast','/group_list','/show_status']

# -----------------------------------------------------------

def send_text(target:str,text:str):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/chat"
        payload = json.dumps({
            "token": wapp_token,
            "to": target,
            "body": text
        })
        response = requests.request("POST", url, headers={'Content-Type': 'application/json'}, data=payload)
        logging.info(response.json())
        return response
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while sending the text using the API.")
        raise WappSenderError(f'{e} - in send_text()')

def send_image(target:str,cap:str,link:str):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/image"
        payload = json.dumps({
            "token": wapp_token,
            "to": target,
            "image": link,
            "caption": cap,
        })
        response = requests.request("POST", url, headers={'Content-Type': 'application/json'}, data=payload)
        logging.info(response.json())
        return response
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while sending the image using the API.")
        raise WappSenderError(f'{e} - in send_image()')

def send_video(target:str,cap:str,link:str):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/video"
        payload = json.dumps({
            "token": wapp_token,
            "to": target,
            "video": link,
            "caption": cap,
        })
        response = requests.request("POST", url, headers={'Content-Type': 'application/json'}, data=payload)
        logging.info(response.json())
        return response
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while sending the video using the API.")
        raise WappSenderError(f'{e} - in send_video()')

def send_document(target:str,cap:str,link:str,docname:str):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/document"
        payload = json.dumps({
            "token": wapp_token,
            "to": target,
            "filename": docname,
            "document": link,
            "caption": cap,
        })
        response = requests.request("POST", url, headers={'Content-Type': 'application/json'}, data=payload)
        logging.info(response.json())
        return response
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while sending the document using the API.")
        raise WappSenderError(f'{e} - in send_document()')

def send_to_groups(ids:list,content:dict,user_id:str):
    try:
        broadcast_op['groups_len']=len(ids)
        for id in ids:
            if broadcast_op['terminate']:
                clear_content()
                thread = Thread(target=terminate, args=(user_id,))
                thread.start()
                break
            else:
                if 'photos' in content:
                    for img in content['photos']:
                        if broadcast_op['terminate']:
                            pass
                        else:
                            send_image(id,'',img)
                if 'videos' in content:
                    if broadcast_op['terminate']:
                        pass
                    else:
                        for vid in content['videos']:
                            send_video(id,'',vid)
                if 'documents' in content:
                    if broadcast_op['terminate']:
                        pass
                    else:
                        for doc_dict in content['documents']:
                            key = list(doc_dict.keys())[0]
                            value = doc_dict[key]
                            send_document(id,'',value,key)
                if 'text' in content and content['text']!=None:
                    if broadcast_op['terminate']:
                        pass
                    else:
                        send_text(id,content['text'])
                broadcast_op['group_count']+=1
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while broadcasting the message and content to the target list")
        raise WappSenderError(f'{e} - in send_to_groups()')

def delete_messages(msgId:str):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/delete"
        payload = json.dumps({
            "token": wapp_token,
            "msgId": msgId
        })

        response = requests.request("POST", url, headers={'Content-Type': 'application/json'}, data=payload)
        return response.json()
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while deleting sent messages using the UltraMsg API.")
        raise WappSenderError(f'{e} - in delete_messages()')
        
def get_groups_dict():
    try:
        url = f"https://api.ultramsg.com/{instance}/groups"

        querystring = {"token": wapp_token}

        response = requests.request("GET", url, headers={'Content-Type': 'application/json'}, params=querystring)
        groups=response.json()
        groups_dict={}
        
        for group in groups:
            groups_dict[group['id']]=group['name']
        return groups_dict
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise WappSenderError(f'{e} - in get_groups_dict()')

def clear_messages(status):
    try:
        url = f"https://api.ultramsg.com/{instance}/messages/clear"
        payload = json.dumps({"token": wapp_token, "status": status})
        requests.post(url, headers={'Content-Type': 'application/json'}, data=payload)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise WappSenderError(f'{e} - in clear_messages()')

def terminate(user_id):
    try:
        clear_messages("queue")
        clear_messages("sent")
        time.sleep(10)
        value = db.collection('WappSender').document('message-ids').get().get('ids')
        for msgId in value:
            delete_messages(msgId)
        send_txt_message(user_id,'Termination process completed')
        broadcast_op['main_loop_mood'] = False
        broadcast_op['terminate']=False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise WappSenderError(f'{e} - in terminate()')

# -----------------------------------------------------------

def bytes_to_mb(byte_size: int) -> float:
    """Convert bytes to megabytes, rounded to two decimal places."""
    return round(byte_size / (1024 * 1024), 2)

def get_file_path(id:str):
    url = f"{telegram_api_url}/getFile?file_id={id}"
    response = requests.get(url)
    file_info = response.json()
    if file_info['ok']:
        file_path = file_info['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        return file_url
    else:
        raise WappSenderError(f"\n{file_info['description']}")

def send_txt_message(chat_id, text):
    try:
        payload = {
            'chat_id': chat_id,
            'text': str(text),
        }
        return requests.post(f"{telegram_api_url}/sendMessage", json=payload).json()
    except Exception as e:
        logging.error(f"An unexpected error: {e} occurred while sending the text message through the Telegram bot.")

def clear_content():
    upload_content_op['content']['photos']=[]
    upload_content_op['content']['videos']=[]
    upload_content_op['content']['documents']=[]
    upload_content_op['content']['text']=None
    upload_content_op['upload_content_mode']=False
    broadcast_op['broadcast_mode']=False
    broadcast_op['group_count']=0
    broadcast_op['groups_len']=0

def send_in_background(target_ids, content, user_id, success_message):
    try:
        broadcast_op['main_loop_mood'] = True
        send_to_groups(target_ids, content,user_id)
        if broadcast_op['terminate']:
            send_txt_message(user_id, "Process of termination in under pocess!!!!")
        else:
            send_txt_message(user_id, success_message)
            broadcast_op['main_loop_mood'] = False
            clear_content()
    except Exception as e:
        logging.error(f"Error: {e}")
        raise WappSenderError(f'{e} - in send_in_background()')

def upload_photo_in_background(update:dict,user_id:str):
    try:
        file=update['message']['photo'][-1]
        file_id=file['file_id']
        file_size=file['file_size']
        file_size_mb=bytes_to_mb(file_size)
        if file_size_mb>15.8:
            send_txt_message(user_id,f"File size too big: {file_size_mb} MB")
            return
        send_txt_message(user_id,f"Photo received: {file_size_mb} MB")
        path=get_file_path(file_id)
        upload_content_op['content']['photos'].append(path)
        logging.info(path)      
    except Exception as e:
        logging.error(f"Error: {e}")
        raise WappSenderError(f'{e} - in upload_photo_in_background()') 
    
def upload_video_in_background(update:dict,user_id:str):
    try:
        file=update['message']['video']
        file_id=file['file_id']
        file_size=file['file_size']
        file_size_mb=bytes_to_mb(file_size)
        if file_size_mb>15.8:
            send_txt_message(user_id,f"File size too big: {file_size_mb} MB")
            return
        send_txt_message(user_id,f"Video received: {file_size_mb} MB")
        path=get_file_path(file_id)
        upload_content_op['content']['videos'].append(path)
        logging.info(path)      
    except Exception as e:
        logging.error(f"Error: {e}")
        raise WappSenderError(f'{e} - in upload_video_in_background()')
    
def upload_document_in_background(update:dict,user_id:str):
    try:
        file=update['message']['document']
        file_id=file['file_id']
        file_size=file['file_size']
        file_size_mb=bytes_to_mb(file_size)
        if file_size_mb>15.8:
            send_txt_message(user_id,f"File size too big: {file_size_mb} MB")
            return
        send_txt_message(user_id,f"Document received: {file_size_mb} MB")
        file_name=file['file_name']
        path=get_file_path(file_id)
        upload_content_op['content']['documents'].append({file_name:path})         
        logging.info(path)      
    except Exception as e:
        logging.error(f"Error: {e}")
        raise WappSenderError(f'{e} - in upload_document_in_background()')
# -----------------------------------------------------------

@app.route('/', methods=['POST'])
def webhook_post():
    update = request.json
    if 'message' in update:
        user_id = update['message']['chat']['id']

        if any(key in update['message'] for key in ["photo", "video", "document"]):
            if upload_content_op['upload_content_mode'] and not broadcast_op['main_loop_mood']:
                if 'photo' in update['message']:
                    try:
                        thread = Thread(target=upload_photo_in_background, args=(update, user_id,))
                        thread.start()
                    except Exception as e:
                            logging.error(f"Unexpected error: {e}")
                            send_txt_message(user_id, f"Error: {e} occurred during the photo upload process")
                            return jsonify({'status': 'ok'})
                        
                elif 'video' in update['message']:
                    try:
                        thread = Thread(target=upload_video_in_background, args=(update, user_id,))
                        thread.start()
                    except Exception as e:
                            logging.error(f"Unexpected error: {e}")
                            send_txt_message(user_id, f"Error: {e} occurred during the video upload process")
                            return jsonify({'status': 'ok'})
                    
                elif 'document' in update['message']:
                    try:
                        thread = Thread(target=upload_document_in_background, args=(update, user_id,))
                        thread.start()
                    except Exception as e:
                            logging.error(f"Unexpected error: {e}")
                            send_txt_message(user_id, f"Error: {e} occurred during the document upload process")
                            return jsonify({'status': 'ok'})
            
        elif 'text' in update['message']:
            text_message=update['message']['text']

            if not broadcast_op['main_loop_mood']:
                if text_message not in bot_commands_list:
                    if login_op['login_mode']:
                        if text_message==wappsender:
                            send_txt_message(user_id,"You are authorized to use the bot.")
                            login_op['login_users'][user_id]=True
                            login_op['login_mode']=False
                        else:
                            send_txt_message(user_id,"Invalid password. Please try again:")

                    elif exclude_op['exclude_mode']:
                        try:
                            message = update['message']['text']
                            list_of_strings = message.split(',')
                            
                            # Validate and convert strings to integers
                            list_of_numbers = [int(num) - 1 for num in list_of_strings]
                            keys_list = list(exclude_op['groups-list'].keys())

                            # Validate indices
                            for index in list_of_numbers:
                                key_to_remove = keys_list[index]
                                exclude_op['exclude_users'].append(key_to_remove)

                            # Construct excluded groups message
                            excluded_groups = ''
                            for group in exclude_op['exclude_users']:
                                excluded_groups += exclude_op['groups-list'][group] + '\n'

                            send_txt_message(user_id, f'Excluded groups are:\n{excluded_groups.strip()}')
                            exclude_op['exclude_mode'] = False

                        except Exception as e:
                            logging.error(f"Unexpected error: {e}")
                            send_txt_message(user_id, f"An unexpected error: {e} occurred while excluding selected groups from the main broadcast list")
                    
                    elif broadcast_op['broadcast_mode']:

                        if text_message == '3':
                            broadcast_op['main_loop_mood'] = True
                            try:
                                send_to_groups(['+917720063009'], upload_content_op['content'],user_id)
                                send_txt_message(user_id, 'The message has been successfully sent to Aditya.')
                                upload_content_op['upload_content_mode'] = True
                                broadcast_op['main_loop_mood'] = False
                            except Exception as e:
                                logging.error(f"Unexpected error: {e}")
                                send_txt_message(user_id, f'Error: {e} occurred while broadcasting content to Aditya')
                                return jsonify({'status': 'ok'})
                        
                        elif text_message == '2':
                            try:
                                if exclude_op['exclude_users']:
                                    target_list = []
                                    for id in get_groups_dict().keys():
                                        if id in exclude_op['exclude_users']:
                                            pass
                                        else:
                                            target_list.append(id)
                                    doc_ref = db.collection('WappSender').document('message-ids')
                                    doc_ref.update({'ids': []})
                                    thread = Thread(target=send_in_background, args=(target_list, upload_content_op['content'], user_id, 'The message has been successfully sent to selected groups.'))
                                    thread.start()
                                    send_txt_message(user_id, 'Request received!.')
                                else:
                                    send_txt_message(user_id, 'Please use the /group_list command to select the groups you wish to exclude from broadcasting.')
                                    broadcast_op['broadcast_mode'] = False
                                    upload_content_op['upload_content_mode'] = True
                            except Exception as e:
                                logging.error(f"Unexpected error: {e}")
                                send_txt_message(user_id, f'Error: {e} occurred while broadcasting content to selected groups')
                                return jsonify({'status': 'ok'})

                        elif text_message == '1':
                            target_list = []
                            try:
                                for id in get_groups_dict().keys():
                                    target_list.append(id)
                                doc_ref = db.collection('WappSender').document('message-ids')
                                doc_ref.update({'ids': []})
                                thread = Thread(target=send_in_background, args=(target_list, upload_content_op['content'], user_id, 'The message has been successfully sent to all groups.'))
                                thread.start()
                                send_txt_message(user_id, 'Request received!.')
                            except Exception as e:
                                logging.error(f"Unexpected error: {e}")
                                send_txt_message(user_id, f'Error: {e} occurred while broadcasting content to all groups')
                                return jsonify({'status': 'ok'})
                        
                    elif upload_content_op['upload_content_mode']:
                        upload_content_op['content']['text']=text_message
                        send_txt_message(user_id,f'Text message received!')

                elif text_message == "/start":
                    if not user_id in login_op['login_users']:
                        send_txt_message(user_id, "Hello! I am WappSender,\nI am here to help you with WhatsApp broadcasting.\nTo get started, please /login to use the bot.")
                    else:
                        send_txt_message(user_id,"Welcome back! You are already logged in.")

                elif text_message == "/login":
                    if user_id in login_op['login_users']:
                        send_txt_message(user_id,"You are already logged in.")
                        return jsonify({'status': 'ok'})
                    send_txt_message(user_id,'Please enter the password to login:')
                    login_op['login_mode']=True
                
                elif text_message == '/upload_content':
                    if user_id not in login_op['login_users']:
                        send_txt_message(user_id,"Please log in first using /login.")
                        return jsonify({'status': 'ok'})
                    clear_content()
                    send_txt_message(user_id,'To send photos, videos, documents, or text messages, please enter the media or text you would like to broadcast.')
                    upload_content_op['upload_content_mode']=True

                elif text_message == '/clear_content':
                    if user_id not in login_op['login_users']:
                        send_txt_message(user_id,"Please log in first using /login.")
                        return jsonify({'status': 'ok'})
                    clear_content()
                    send_txt_message(user_id,'The media list has been successfully cleared.')

                elif text_message == '/broadcast':
                    if not upload_content_op['upload_content_mode']:
                        send_txt_message(user_id,"No content has been uploaded yet. Please use the /upload_content command to upload content before proceeding with the broadcast.")
                        return jsonify({'status': 'ok'})
                    upload_content_op['upload_content_mode']=False
                    send_txt_message(user_id,'1. Send a message to all groups\n2. Send a message to selected groups\n3. Send a message to Aditya')
                    broadcast_op['broadcast_mode']=True
                    
                elif text_message == '/group_list':
                    try:
                        if user_id not in login_op['login_users']:
                            send_txt_message(user_id,"Please log in first using /login.")
                            return jsonify({'status': 'ok'})
                        exclude_op['groups-list']=get_groups_dict()
                        exclude_op['exclude_users'].clear()
                        output_string_1 = ''
                        output_string_2=''
                        # Building the output string
                        for index, value in enumerate(exclude_op['groups-list'].values()):
                            if index<100:
                                output_string_1 += f"{index+1}:  {value}\n"
                            else:
                                output_string_2 += f"{index+1}:  {value}\n"
                        exclude_op['exclude_mode']=True
                        send_txt_message(user_id,output_string_1)
                        send_txt_message(user_id,output_string_2)
                        send_txt_message(user_id,'Please provide the indices of the groups you wish to exclude from the broadcast, separated by commas (e.g., 1,2,3).')
                    except Exception as e:
                        logging.error(f"Unexpected error: {e}")
                        send_txt_message(user_id, f"Error: {e} occurred while updating the group list using the /group_list command.")
                        return jsonify({'status': 'ok'})

            else:
                if text_message == "/show_status" :
                    send_txt_message(user_id, f"{broadcast_op['group_count']}/{broadcast_op['groups_len']}")
                
                elif text_message == "/terminate":
                    broadcast_op['terminate']=True
    
    return jsonify({'status': 'ok'})

@app.route('/health', methods=['GET'])
def health_check():
    response = jsonify({'status': 'ok', 'message': 'Service is healthy'})
    response.headers['Content-Type'] = 'application/json'
    return response, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)