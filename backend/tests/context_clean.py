from core.engine.memory import RedisClient

def clean_context():
    redis_instance = RedisClient()
    if redis_instance.client is None:
        print("❌ Could not connect to Redis. Is it running?")
        return

    redis = redis_instance.get_client()
    
    # Keys to look for
    patterns = ["neuron_role:*", "context:*"]
    
    print("🧹 cleaning Neural Memory...")
    
    count = 0
    for pattern in patterns:
        cursor = '0'
        while cursor != 0:
            cursor, keys = redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                redis.delete(*keys)
                count += len(keys)
                for key in keys:
                    print(f"   Deleted: {key.decode('utf-8')}")
            
    print(f"✅ Cleaned {count} keys from Neural Memory.")

if __name__ == "__main__":
    clean_context()
