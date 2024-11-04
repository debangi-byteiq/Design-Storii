import os
import boto3
from dotenv import load_dotenv


load_dotenv()



# MySQL RDS Config
DB_USER = os.getenv("DB_USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
DATABASE = os.getenv("DATABASE")
TABLE_NAME = os.getenv("TABLE_NAME")
POOL_RECYCLE = int(os.getenv("POOL_RECYCLE"))
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{PASSWORD}@{HOST}/{DATABASE}"

# S3 Bucket config
bucket_name = os.getenv("BUCKET")
bucket_path = os.getenv("BUCKET_PATH")
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-1')
s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)


