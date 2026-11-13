if redis.call('EXISTS', KEYS[2]) == 1 then
    return 0
end

local owns_enqueue = redis.call('GET', KEYS[1]) == ARGV[1]
local ttl = tonumber(ARGV[4])
if ttl == 0 then
    if owns_enqueue then
        ttl = redis.call('PTTL', KEYS[1])
    end
    if ttl <= 0 then
        ttl = tonumber(ARGV[3])
    end
end

redis.call('SET', KEYS[2], ARGV[2], 'PX', ttl)
if owns_enqueue then
    redis.call('PEXPIRE', KEYS[1], ttl)
elseif redis.call('EXISTS', KEYS[1]) == 0 then
    redis.call('SET', KEYS[1], ARGV[1], 'PX', ttl)
end
return 1
