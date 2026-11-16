if redis.call('GET', KEYS[2]) ~= ARGV[2] then
    return 0
end

redis.call('PEXPIRE', KEYS[2], ARGV[3])
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('PEXPIRE', KEYS[1], ARGV[3])
end
return 1
