"""
Clear Redis cache for system prompts and context.
Run this before test.py to ensure fresh prompt generation.
"""
from core.engine.memory import RedisClient

def clear_redis_cache():
    redis_instance = RedisClient()
    redis_client = redis_instance.get_client()
    
    print("🧹 Clearing Redis cache...")
    
    # Clear all keys
    keys = redis_client.keys("*")
    if keys:
        for key in keys:
            redis_client.delete(key)
        print(f"✅ Cleared {len(keys)} Redis keys")
    else:
        print("✅ Redis already empty")

if __name__ == "__main__":
    clear_redis_cache()
