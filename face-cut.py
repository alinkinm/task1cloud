import boto3
import cv2
import json
import io
import random
import string
import os
import ydb
import ydb.iam

def handler(event, context):

    # client = boto3.client('sqs', region_name='ru-central1', endpoint_url='https://message-queue.api.cloud.yandex.net/')
    # #queue_url = 'https://message-queue.api.cloud.yandex.net/b1g71e95h51okii30p25/dj60000000140qj702mk/vvot03-task'
    # #queue_url = 'https://message-queue.api.cloud.yandex.net/b1g71e95h51okii30p25/dj60000000149icm02mk/Testqueue'
    # queue_url='https://message-queue.api.cloud.yandex.net/b1g71e95h51okii30p25/dj60000000149qaq02mk/testqueue'
    # messages = client.receive_message(
    #     QueueUrl=queue_url,
    #     AttributeNames=[
    #     'All'
    # ],
    # MessageAttributeNames=[
    #     'key', 'bucket_id', 'vertices'
    # ],
    # MaxNumberOfMessages=10,
    # VisibilityTimeout=60,
    # WaitTimeSeconds=20,
    # ReceiveRequestAttemptId='string'
    # ).get('Messages')

    # for msg in messages:
    #     print('Received message: "{}"'.format(msg))

    # for msg in messages:
    #     client.delete_message(
    #         QueueUrl=queue_url,
    #         ReceiptHandle=msg.get('ReceiptHandle')
    #     )
    #     print('Successfully deleted message by receipt handle "{}"'.format(msg.get('ReceiptHandle')))

        # print(event)
    attributes = event['messages'][0]['details']['message']['message_attributes']
    print(attributes)
    key = attributes['key']['string_value']
    print(key)

    bucket_id = attributes['bucket_id']['string_value']

    vertices_string = attributes['vertices']['string_value']
    vertices = json.loads(vertices_string)['vertices']
    print(vertices)

    
    session = boto3.session.Session()
    s3 = session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net'
    )
    
    object = s3.get_object(Bucket=bucket_id,Key=key)
    print(object)
    body = object['Body']
    
    with io.FileIO('/tmp/sample.png', 'w') as file:
        for b in body._raw_stream:
            file.write(b)
    
    f = open('/tmp/sample.png', "rb")
    
    image = cv2.imread(r"/tmp/sample.png")
    
    x1, y1 = int(vertices[0]['x']), int(vertices[0]['y'])
    x2, y2 = int(vertices[1]['x']), int(vertices[1]['y'])
    x3, y3 = int(vertices[2]['x']), int(vertices[2]['y'])
    x4, y4 = int(vertices[3]['x']), int(vertices[3]['y'])
    
    top_left_x = min([x1, x2, x3, x4])
    top_left_y = min([y1, y2, y3, y4])
    bot_right_x = max([x1, x2, x3, x4])
    bot_right_y = max([y1, y2, y3, y4])
    
    crop_image = image[top_left_y:bot_right_y+1, top_left_x:bot_right_x+1]

    cv2.imwrite('/tmp/sample.png',crop_image)
    #cv2.imshow("cropped", crop_image)

    #загрузить в бакет
    letters = string.ascii_lowercase
    object_name = (''.join(random.choice(letters) for i in range(10)))
    object_name = object_name +'.png'
    print(object_name)
    response = s3.upload_file("/tmp/sample.png", 'vvot03-faces', object_name)
    print(response)

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

    session.transaction().execute(
        'UPSERT INTO photo_originals (original_key, cut_key, has_name) VALUES ("'+key+'", "'+object_name+'", false);',
        commit_tx=True,
    )



    # ydb_client = boto3.client('dynamodb',
    # region_name='ru-central1',
    # endpoint_url=os.getenv('DATABASE_URL'),
    # aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID'),
    # aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY'))
    #
    # response = ydb_client.put_item(
    #     TableName = 'photo_originals',
    #     Item = {
    #         'original_key': {
    #             'S': key
    #         },
    #         'cut_key': {
    #             'S': object_name
    #         }
    #     }
    # )
    #
    # print(response)
