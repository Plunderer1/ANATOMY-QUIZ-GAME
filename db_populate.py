import mysql.connector

def insert_questions():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Hatdog555',
            database='anatomy_quiz_game'
        )
        cursor = conn.cursor()
        
        with open('tf_questions.sql', 'r') as f:
            sql_file = f.read()
            # Split by semicolon, but be careful with empty ones
            commands = [cmd.strip() for cmd in sql_file.split(';') if cmd.strip()]
            
            for command in commands:
                print(f"Executing: {command[:50]}...")
                cursor.execute(command)
                conn.commit()
        
        print("TF questions inserted successfully")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    insert_questions()
