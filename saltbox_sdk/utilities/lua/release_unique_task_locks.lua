local released = 0
for i = 1, #KEYS do
    if ARGV[i] ~= '' and redis.call('GET', KEYS[i]) == ARGV[i] then
        released = released + redis.call('DEL', KEYS[i])
    end
end
return released
