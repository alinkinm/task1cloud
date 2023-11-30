import boto3
import json
import base64
import requests
import os
import io
import time
import jwt
from requests_auth_aws_sigv4 import AWSSigV4
from aws_requests_auth.aws_auth import AWSRequestsAuth


def encode_file(file):
    file_content = file.read()
    return base64.b64encode(file_content)


def handler(event, context):
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )

    up = event
    messages = up["messages"]
    details = messages[0]['details']
    bucket_id = details["bucket_id"]
    key = details["object_id"]

    metadata = messages[0]['event_metadata']
    folder_id = metadata['folder_id']

    object = s3.get_object(Bucket=bucket_id, Key=key)
    body = object['Body']

    with io.FileIO('/tmp/sample.jpg', 'w') as file:
        for b in body._raw_stream:
            file.write(b)

    f = open('/tmp/sample.jpg', "rb")
    encoded_file = encode_file(f)

    x = {
        "folderId": str(folder_id),
        "analyze_specs": [{
            "content": encoded_file.decode(),
            "features": [{
                "type": "FACE_DETECTION"
            }]

        }]
    }

    y = json.dumps(x)

    url = 'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token'
    headers = {'Metadata-Flavor': 'Google'}
    resp = requests.get(url, headers=headers)
    tok = resp.content.decode('UTF-8')
    print(tok)
    json_tok = json.loads(tok)

    url = 'https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze'
    headers = {
        'Content-type': 'application/json',
        'Authorization': "Bearer " + json_tok["access_token"],
    }
    response = requests.post(url, headers=headers, data=y)

    print(response.json())
    faceDetection = response.json()['results'][0]['results'][0]['faceDetection']
    if str(faceDetection) == '{}':
        return

    faces = faceDetection['faces']

    sqs = boto3.client('sqs', region_name='ru-central1', endpoint_url='https://message-queue.api.cloud.yandex.net/')
    queue_url = os.getenv('QUEUE_URL')
    for face in faces:
        response = sqs.send_message(
            QueueUrl=queue_url,
            DelaySeconds=10,
            MessageAttributes={
                'key': {
                    'DataType': 'String',
                    'StringValue': key
                },
                'bucket_id': {
                    'DataType': 'String',
                    'StringValue': bucket_id
                },
                'vertices': {
                    'DataType': 'String',
                    'StringValue': str(json.dumps(face['boundingBox']))
                }},
            MessageBody=('body')
        )
        print(response)
