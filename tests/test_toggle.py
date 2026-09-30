"""Exercise the shipped Lua against game API doubles; run with Python + lupa."""
import json
import unittest
from pathlib import Path
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mod/zomboid_mic_toggle/42/media/lua/client/So4MicToggle.lua'


class ToggleTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
            require = function() end
            isServer = function() return false end
            client, dead, paused, typing, enabled, serverVoice = true, false, false, false, true, true
            mode, changes, eaten, now = 1, 0, 0, 1000
            keys = {}
            Keyboard = {KEY_T=20, KEY_RETURN=28, KEY_LCONTROL=29, KEY_RCONTROL=157, KEY_LMENU=56,
                        KEY_RMENU=184, KEY_LSHIFT=42, KEY_RSHIFT=54}
            GameKeyboard = {eatKeyPress=function(key) eaten=eaten+1 end}
            core = {
                getOptionVoiceMode=function() return mode end,
                setOptionVoiceMode=function(_,value) mode=value; changes=changes+1 end,
                getOptionVoiceEnable=function() return enabled end,
                isDoingTextEntry=function() return typing end,
                getScreenWidth=function() return 1280 end,
            }
            getCore=function() return core end
            getServerOptions=function() return {getBoolean=function() return serverVoice end} end
            player={isDead=function() return dead end}
            getPlayer=function() return player end
            isClient=function() return client end
            isGamePaused=function() return paused end
            isKeyDown=function(key) return keys[key] == true end
            getTimestampMs=function() return now end
            getText=function(key) return key end
            getTextManager=function() return {MeasureStringX=function() return 120 end} end
            UIFont={Small=1}
            ISChat={focused=false}
            ISChat.instance={focus=function() ISChat.focused=true; typing=true end}
            ISPanel={new=function()
                return setmetatable({}, {__index=function(_,key) return function() end end})
            end}
            Events=setmetatable({}, {__index=function(t,key)
                local handlers={}
                local event={Add=function(fn) handlers[#handlers+1]=fn end,
                             trigger=function(...) for _,fn in ipairs(handlers) do fn(...) end end}
                rawset(t,key,event); return event
            end})
            print=function() end
        ''')
        self.lua.execute(SOURCE.read_text(encoding='utf-8'))
        self.g = self.lua.globals()

    def start(self):
        self.g.Events.OnGameStart.trigger()
        self.assertEqual(self.g.mode, 3)

    def press(self, key=20):
        self.g.Events.OnKeyStartPressed.trigger(key)

    def test_latched_state_survives_release_repeat_and_ticks(self):
        self.start()
        self.press()
        self.assertEqual(self.g.mode, 2)
        changes = self.g.changes
        for _ in range(100):
            self.g.Events.OnKeyKeepPressed.trigger(20)
            self.g.Events.OnTick.trigger()
        self.g.Events.OnKeyPressed.trigger(20)
        self.assertEqual(self.g.mode, 2)
        self.assertEqual(self.g.changes, changes)
        self.press()
        self.assertEqual(self.g.mode, 3)
        self.assertEqual(self.g.eaten, 2)
        self.assertTrue(self.g.enabled, 'muting must preserve reception')

    def test_chat_text_fields_menus_modifiers_and_other_keys_are_ignored(self):
        self.start()
        for variable in ('typing', 'paused', 'dead'):
            self.g[variable] = True
            self.press()
            self.g[variable] = False
        self.g.ISChat.focused = True
        self.press()
        self.g.ISChat.focused = False
        for key in (29,157,56,184,42,54):
            self.g['keys'][key] = True
            self.press()
            self.g['keys'][key] = False
        self.press(28)
        self.assertEqual(self.g.mode, 3)
        self.assertEqual(self.g.eaten, 0)

    def test_death_mutes_and_respawn_does_not_reopen_microphone(self):
        self.start()
        self.press()
        self.g.dead = True
        self.g.Events.OnPlayerDeath.trigger(self.g.player)
        self.assertEqual(self.g.mode, 3)
        self.press()
        self.g.dead = False
        self.g.Events.OnTick.trigger()
        self.assertFalse(self.g.So4MicToggle.isOn())

    def test_enter_opens_chat_without_t_toggling_while_typing(self):
        self.start()
        self.press()
        self.g.Events.OnKeyPressed.trigger(28)
        self.assertTrue(self.g.ISChat.focused)
        self.press()
        self.assertEqual(self.g.mode, 2)
        self.assertEqual(self.g.eaten, 1)

    def test_respawn_recovers_after_player_is_temporarily_missing(self):
        self.start()
        self.press()
        player = self.g.player
        self.g.player = None
        self.g.Events.OnTick.trigger()
        self.assertFalse(self.g.So4MicToggle.isOn())
        self.g.player = player
        self.g.Events.OnTick.trigger()
        self.assertEqual(self.g.mode, 3)
        self.press()
        self.assertEqual(self.g.mode, 2)

    def test_disabled_voice_never_claims_on_or_enables_voip(self):
        for setting in ('enabled', 'serverVoice'):
            self.g[setting] = False
            self.start()
            self.press()
            self.assertFalse(self.g.So4MicToggle.isOn())
            self.assertEqual(self.g.mode, 3)
            self.assertFalse(self.g[setting])
            self.g[setting] = True

    def test_session_restores_original_mode_and_reconnect_starts_muted(self):
        self.start()
        self.press()
        self.g.Events.OnMainMenuEnter.trigger()
        self.assertEqual(self.g.mode, 1)
        self.assertFalse(self.g.So4MicToggle.isOn())
        self.press()
        self.assertEqual(self.g.mode, 1)
        self.start()
        self.assertEqual(self.g.mode, 3)

    def test_external_ptt_setting_and_disabled_voice_are_synchronized(self):
        self.start()
        self.g.mode = 1
        self.g.Events.OnTick.trigger()
        self.assertEqual(self.g.mode, 3)
        self.press()
        self.g.enabled = False
        self.g.Events.OnTick.trigger()
        self.assertEqual(self.g.mode, 3)

    def test_single_player_is_untouched_and_setter_failure_not_reported_as_on(self):
        self.g.client = False
        self.g.Events.OnGameStart.trigger()
        self.press()
        self.assertEqual(self.g.mode, 1)
        self.g.client = True
        self.start()
        self.lua.execute('core.setOptionVoiceMode=function() error("test failure") end')
        self.assertFalse(self.g.So4MicToggle.toggle())
        self.assertFalse(self.g.So4MicToggle.isOn())

    def test_translations_have_the_same_keys(self):
        base=ROOT/'mod/zomboid_mic_toggle/42/media/lua/shared/Translate'
        ko=json.loads((base/'KO/UI.json').read_text(encoding='utf-8'))
        en=json.loads((base/'EN/UI.json').read_text(encoding='utf-8'))
        self.assertEqual(ko.keys(),en.keys())


if __name__ == '__main__':
    unittest.main()
