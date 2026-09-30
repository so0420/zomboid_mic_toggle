-- Client-only microphone transmission control for Project Zomboid Build 42.
if isServer() then return end
require "ISUI/ISPanel"

So4MicToggle = So4MicToggle or {}
local Mic = So4MicToggle
Mic.VERSION = "1.0.0"
local OPEN_MIC, LISTEN_ONLY = 2, 3
local active, previousMode, panel = false, nil, nil
local message, messageUntil = nil, 0

local function localPlayer()
    if not isClient() then return nil end
    return getPlayer()
end

local function voiceAvailable()
    if not getCore():getOptionVoiceEnable() then return false end
    local options = getServerOptions()
    return not options or options:getBoolean("VoiceEnable")
end

local function setMode(mode)
    local ok = pcall(function() getCore():setOptionVoiceMode(mode) end)
    return ok and getCore():getOptionVoiceMode() == mode
end

local function notice(key)
    message, messageUntil = getText(key), getTimestampMs() + 4000
end

function Mic.isOn()
    return active and voiceAvailable() and getCore():getOptionVoiceMode() == OPEN_MIC
end

function Mic.toggle()
    local player = localPlayer()
    if not active or not player or player:isDead() then return false end
    if not voiceAvailable() then
        setMode(LISTEN_ONLY)
        notice("UI_So4Mic_EnableVoice")
        return false
    end
    local target = Mic.isOn() and LISTEN_ONLY or OPEN_MIC
    if not setMode(target) then
        notice("UI_So4Mic_Error")
        return false
    end
    message = nil
    print("[zomboid_mic_toggle] microphone " .. (target == OPEN_MIC and "ON" or "OFF"))
    return true
end

function Mic.onKeyStartPressed(key)
    if key ~= Keyboard.KEY_T or not active then return end
    local player = localPlayer()
    if not player or player:isDead() or isGamePaused() then return end
    if getCore():isDoingTextEntry() or (ISChat and ISChat.focused) then return end
    for _, modifier in ipairs({Keyboard.KEY_LCONTROL, Keyboard.KEY_RCONTROL,
            Keyboard.KEY_LMENU, Keyboard.KEY_RMENU, Keyboard.KEY_LSHIFT, Keyboard.KEY_RSHIFT}) do
        if isKeyDown(modifier) then return end
    end
    -- Vanilla chat opens on key release. Consume this press/release without
    -- changing the user's saved chat bindings; Enter can still open chat.
    GameKeyboard.eatKeyPress(key)
    Mic.toggle()
end

-- Some B42 versions bind Enter as alternate chat but never handle that binding.
-- Keep chat reachable after T is consumed, and focus on release like vanilla.
function Mic.onKeyPressed(key)
    if key ~= Keyboard.KEY_RETURN or not active then return end
    local player = localPlayer()
    if not player or player:isDead() or isGamePaused() then return end
    if getCore():isDoingTextEntry() or not ISChat or ISChat.focused then return end
    for _, modifier in ipairs({Keyboard.KEY_LCONTROL, Keyboard.KEY_RCONTROL,
            Keyboard.KEY_LMENU, Keyboard.KEY_RMENU, Keyboard.KEY_LSHIFT, Keyboard.KEY_RSHIFT}) do
        if isKeyDown(modifier) then return end
    end
    if ISChat.instance then ISChat.instance:focus() end
end

local function showPanel()
    if panel then return end
    panel = ISPanel:new(0, 16, 180, 30)
    panel:initialise()
    panel:instantiate()
    panel:setAlwaysOnTop(true)
    panel.prerender = function(self)
        local on = Mic.isOn()
        local available = voiceAvailable()
        local text = getText(on and "UI_So4Mic_On" or "UI_So4Mic_Off")
        if not available then text = getText("UI_So4Mic_Unavailable") end
        if message and getTimestampMs() < messageUntil then text = message end
        local width = math.max(180, getTextManager():MeasureStringX(UIFont.Small, text) + 36)
        self:setWidth(width)
        self:setX(math.floor((getCore():getScreenWidth() - width) / 2))
        local r, g, b = 0.65, 0.67, 0.7
        if on then r, g, b = 0.4, 0.9, 0.5 end
        self:drawRect(0, 0, width, 30, 0.85, 0.07, 0.08, 0.09)
        self:drawRectBorder(0, 0, width, 30, 0.8, r, g, b)
        self:drawRect(10, 12, 6, 6, 1, r, g, b)
        self:drawText(text, 23, 6, r, g, b, 1, UIFont.Small)
    end
    panel:addToUIManager()
end

function Mic.start()
    if active or not localPlayer() then return end
    previousMode = getCore():getOptionVoiceMode()
    active = true
    setMode(LISTEN_ONLY)
    showPanel()
    print("[zomboid_mic_toggle] ready; T toggles microphone; initial state OFF")
end

function Mic.stop()
    if not active then return end
    active = false
    -- Stop transmitting before restoring the pre-session preference in menus.
    setMode(LISTEN_ONLY)
    if previousMode then setMode(previousMode) end
    previousMode, message = nil, nil
    if panel then panel:removeFromUIManager(); panel = nil end
end

function Mic.onPlayerDeath(player)
    if active and player == getPlayer() then setMode(LISTEN_ONLY) end
end

function Mic.onTick()
    if not active then
        -- Respawning can briefly remove the player without another OnGameStart.
        local player = localPlayer()
        if player and not player:isDead() then Mic.start() end
        return
    end
    local player = localPlayer()
    if not player then Mic.stop(); return end
    local mode = getCore():getOptionVoiceMode()
    -- Changing audio options must not leave PTT active while the badge says OFF.
    if mode == 1 or ((player:isDead() or not voiceAvailable()) and mode ~= LISTEN_ONLY) then
        setMode(LISTEN_ONLY)
    end
end

Events.OnGameStart.Add(Mic.start)
Events.OnKeyStartPressed.Add(Mic.onKeyStartPressed)
Events.OnKeyPressed.Add(Mic.onKeyPressed)
Events.OnTick.Add(Mic.onTick)
Events.OnPlayerDeath.Add(Mic.onPlayerDeath)
Events.OnMainMenuEnter.Add(Mic.stop)
