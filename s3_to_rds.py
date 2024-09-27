import pandas as pd
import boto3
import os
import json
import pymysql

def extract_datetime(df):
    df['start'] = df['message'].str.find('[') + 1  # Find the position of "[" and move 1 character forward
    df['extracted'] = df.apply(lambda row: row['message'][row['start']:row['start']+15] if row['start'] > 0 else None, axis=1)
    df['extracted'] = df['extracted'].str.replace(']', '')  # Remove brackets
    df['extracted'] = pd.to_datetime(df['extracted'], format='%d/%m/%Y %H:%M', errors='coerce')
    df = df.drop(columns=['start'])
    return df

def lambda_handler(event, context):
    json_file_url = os.environ.get('JSON_URL')  # Assuming this is the S3 key (path to the file)
    db_pass = os.environ.get('DB_PASSWORD')

    s3_client = boto3.client('s3')
    
    s3_response = s3_client.get_object(Bucket='telegram-scrape-proj', Key='telegram_messages.json')
    file_content = s3_response['Body'].read().decode('utf-8')
    
    # Parse the JSON content (list of strings) and create a DataFrame
    json_data = json.loads(file_content)
    df = pd.DataFrame(json_data, columns=["message"])

    # DataFrame transformation logic
    df['event'] = df['message'].apply(lambda x: x.split('[')[0] if '[' in x else None)
    df['event'] = df['event'].str.replace(r'[^\u0590-\u05FF ]', '', regex=True)

    df['area'] = df['message'].str.extract(r'(אזור.*)', expand=False).str.replace('אזור', '')
    df['area'] = df['area'].str.replace(r'[^\u0590-\u05FF ]', '', regex=True)

    df = extract_datetime(df)

    df['message_lines'] = df['message'].apply(lambda x: x.split('\n'))
    df['processed_lines'] = [[] for _ in range(len(df))]

    for index, lines in df['message_lines'].items():
        start_processing = False  
        processed_lines = []  

        for line in lines:  
            if 'אזור' in line and '**' in line:
                start_processing = True  
                continue

            if start_processing:
                processed_lines.append(line)
            
            if start_processing and not line.strip():
                break

        df.at[index, 'processed_lines'] = processed_lines

    df = df.explode('processed_lines')  
    df.rename(columns={'processed_lines': 'city'}, inplace=True)
    df.rename(columns={'extracted': 'datetime'}, inplace=True)
    df.drop(columns={'message_lines'}, inplace=True)
    
    # Handle NaN values by replacing them with None (which corresponds to NULL in MySQL)
    df = df.where(pd.notnull(df), None)

    # Connect to MySQL RDS using pymysql
    conn = pymysql.connect(
        host='telegram-proj-mysql.c1ieseas0opv.us-east-1.rds.amazonaws.com',  # RDS endpoint
        user='admin',  # MySQL username
        password=db_pass,  
        database='telegram',  # MySQL database name
        cursorclass=pymysql.cursors.DictCursor
    )
    
   
    with conn.cursor() as cursor:
        
        #Step 0: truncate temp 
        cursor.execute("""
            TRUNCATE  temp_telegram_data;
        """)
        
        #step 1
        insert_sql = """
        INSERT INTO temp_telegram_data (message, event, area, datetime, city)
        VALUES (%s, %s, %s, %s, %s)
        """
        # Convert DataFrame to a list of tuples (for executemany)
        data_to_insert = df[['message', 'event', 'area', 'datetime', 'city']].values.tolist()

        # Insert the data
        cursor.executemany(insert_sql, data_to_insert)
        
        # Step 2: Insert only the rows with datetime greater than the max(datetime) in the main table
        cursor.execute("""
            INSERT INTO telegram_data (message, event, area, datetime, city)
            SELECT t.message, t.event, t.area, t.datetime, t.city
            FROM temp_telegram_data t
            LEFT JOIN telegram_data td ON t.datetime = td.datetime
            WHERE t.datetime > (SELECT COALESCE(MAX(datetime), '1970-01-01') FROM telegram_data);
        """)
        
    # Commit the transaction
    conn.commit()

    # Close the connection
    conn.close()

    return {
        'statusCode': 200,
        'body': "DataFrame processed and inserted into MySQL successfully"
    }
