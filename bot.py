import json
import requests
import os
import ydb
import ydb.iam
import boto3
import random
import io


def handler(event, context):
    tgkey = os.environ["TGKEY"]
    update = json.loads(event["body"])
    message = update["message"]
    message_id = message["message_id"]
    chat_id = message["chat"]["id"]
    print(message)

    if "reply_to_message" in message:
        print(message['text'])
        old_name = message['reply_to_message']['caption']
        new_name = message['text']

        full_database = os.getenv('DATABASE_URL')
        endpoint = full_database.split('/?database=')[0]
        database = full_database.split('/?database=')[1]

        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials(),
        )

        driver.wait(fail_fast=True, timeout=10)

        try:
            session = driver.table_client.session().create()
            print("хочу заменить ", old_name, "на ", new_name)
            results = session.transaction().execute(
                'UPDATE photo_originals SET has_name=true, name = "'+new_name+'" WHERE cut_key = "'+old_name+'";',
                commit_tx=True,
            )
        except GenericError:
            url = f"https://api.telegram.org/bot{tgkey}/sendMessage"
            params = {"chat_id": chat_id,
                      "text": "У этого лица уже есть имя. Проверьте свой ответ на сообщение с лицом",
                      "reply_to_message_id": message_id}
            r = requests.get(url=url, params=params)


        # url_get_file = f"https://api.telegram.org/bot{tgkey}/getFile"
        # r_file = requests.get(url=url_get_file, params={"file_id": file_id})
        # print('текст - ' + r_file.text)
        # file_ob = r_file.json()
        #
        # file_path = file_ob["result"]["file_path"]
        # url_voice = f"https://api.telegram.org/file/bot{tgkey}/{file_path}"
        #
        # r_img = requests.get(url=url_voice)
        #
        # with open("/tmp/sample.png", 'wb') as f:
        #     f.write(r_img)
        #


        # prev_msg = message["reply_to_message"]
        # new_name = message['text']
        # new_name = new_name + ".png"

        # full_database = os.getenv('DATABASE_URL')
        # endpoint = full_database.split('/?database=')[0]
        # database = full_database.split('/?database=')[1]

        # driver = ydb.Driver(
        #     endpoint=endpoint,
        #     database=database,
        #     credentials=ydb.iam.MetadataUrlCredentials(),
        # )

        # driver.wait(fail_fast=True, timeout=5)

        # session = driver.table_client.session().create()
        # results = session.transaction().execute(
        #     'UPDATE photo_originals SET name = ' + new_name + ' WHERE cut_key =' + os.environ["CUT_KEY"] + ';',
        #     commit_tx=True,
        # )

    elif message['text'] == '/getface':
        full_database = os.getenv('DATABASE_URL')
        endpoint = full_database.split('/?database=')[0]
        database = full_database.split('/?database=')[1]

        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials(),
        )

        driver.wait(fail_fast=True, timeout=5)

        session = driver.table_client.session().create()

        results = session.transaction().execute(
            'SELECT original_key, cut_key FROM photo_originals WHERE has_name == false;',
            commit_tx=True,
        )

        if len(results[0].rows)==0:
            url = f"https://api.telegram.org/bot{tgkey}/sendMessage"
            params = {"chat_id": chat_id,
                      "text": "Не осталось неопознанных лиц",
                      "reply_to_message_id": message_id}
            r = requests.get(url=url, params=params)
        else:
            max = len(results[0].rows)
            number = random.randint(0, max - 1)

            print(results[0].rows)

            cut_key = results[0].rows[number].cut_key
            original_key = results[0].rows[number].original_key

            print("original_key: ", original_key, "cut_key: ", cut_key)

            session = boto3.session.Session()
            s3 = session.client(
                service_name='s3',
                endpoint_url='https://storage.yandexcloud.net'
            )

            object = s3.get_object(Bucket=os.getenv('FACE_STORAGE'), Key=cut_key)
            print(object)
            body = object['Body']

            with io.FileIO('/tmp/sample.jpg', 'w') as file:
                for b in body._raw_stream:
                    file.write(b)

            f = open('/tmp/sample.jpg', "rb")

            api_url = 'https://d5d2hcevr9cjdgicqn41.apigw.yandexcloud.net/?face=' + cut_key
            url = f"https://api.telegram.org/bot{tgkey}/sendPhoto?chat_id={chat_id}"

            params = {"caption": cut_key}
            r = requests.post(url=url, files={'photo': f}, params=params)
            print(r.text)
    elif '/find ' in message['text']:
        namae = message['text'].split(" ")[1]

        full_database = os.getenv('DATABASE_URL')
        endpoint = full_database.split('/?database=')[0]
        database = full_database.split('/?database=')[1]

        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials(),
        )

        driver.wait(fail_fast=True, timeout=5)

        session = driver.table_client.session().create()

        results = session.transaction().execute(
            'SELECT original_key FROM photo_originals WHERE name == "'+namae+'";',
            commit_tx=True,
        )

        if len(results[0].rows) ==0:
            rep_text = f"Фотографии с {namae} не найдены"
            url = f"https://api.telegram.org/bot{tgkey}/sendMessage"
            params = {"chat_id": chat_id,
                      "text": rep_text,
                      "reply_to_message_id": message_id}
            r = requests.get(url=url, params=params)
        else:
            for row in results[0].rows:
                orig_key = row.original_key

                session = boto3.session.Session()
                s3 = session.client(
                    service_name='s3',
                    endpoint_url='https://storage.yandexcloud.net'
                )

                object = s3.get_object(Bucket=os.getenv('PHOTO_STORAGE'), Key=orig_key)
                body = object['Body']

                with io.FileIO('/tmp/sample.jpg', 'w') as file:
                    for b in body._raw_stream:
                        file.write(b)

                f = open('/tmp/sample.jpg', "rb")

                url = f"https://api.telegram.org/bot{tgkey}/sendPhoto?chat_id={chat_id}"

                r = requests.post(url=url, files={'photo': f})

    else:
        url = f"https://api.telegram.org/bot{tgkey}/sendMessage"
        params = {"chat_id": chat_id,
                  "text": "Ошибка",
                  "reply_to_message_id": message_id}
        r = requests.get(url=url, params=params)








            #     rep_text = text.upper()
    # elif "photo" in message:
    #     rep_text = "Красивая картинка!"
    # elif "voice" in message:
    #     voice = message["voice"]
    #     file_id = voice["file_id"]
    #     url_get_file = f"https://api.telegram.org/bot{tgkey}/getFile"
    #     r_file = requests.get(url=url_get_file, params={"file_id": file_id})
    #     print('текст - ' + r_file.text)
    #     file_ob = r_file.json()
    #     file_path = file_ob["result"]["file_path"]
    #     url_voice = f"https://api.telegram.org/file/bot{tgkey}/{file_path}"
    #     r_voice = requests.get(url=url_voice)
    #     voce_data = r_voice.content
    #     url_ys = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    #     params_ys = {"topic": "general", "folderId": "b1gqqiji145iks917iem"}
    #     auth_ys = {"Authorization": f"Bearer {context.token['access_token']}"}
    #     r_ys = requests.post(url=url_ys, headers=auth_ys, params=params_ys, data=voce_data)
    #     rep_text = r_ys.text
    #     print(rep_text)
    # else:
    #     rep_text = "Я вас не понимать!"
    # url = f"https://api.telegram.org/bot{tgkey}/sendMessage"
    # params = {"chat_id": chat_id,
    #           "text": rep_text,
    #           "reply_to_message_id": message_id}
    # r = requests.get(url=url, params=params)
    #
    # print(r.text)
    # print(context.token["access_token"])
    # return {
    #     'statusCode': 200,
    # }
