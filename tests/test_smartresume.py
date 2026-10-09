import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from handlers.dalet_slash_commands import SlashCommands


class TestSmartResume(unittest.IsolatedAsyncioTestCase):
    """Pruebas unitarias para el comando /resumir y formateo de historial de chat."""

    def setUp(self):
        self.bot = MagicMock()
        self.bot.nlp_service = MagicMock()
        self.bot.nlp_service.generate_reply = AsyncMock(return_value="### 📌 En pocas palabras (TL;DR)\nTodo en orden.")
        self.cog = SlashCommands(self.bot)

    async def test_slash_resumir_cooldown(self):
        """Verifica que el cooldown anti-spam evite ejecuciones repetidas inmediatas."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()

        # Primera llamada registra cooldown
        self.cog._check_cooldown("resumir:123456", 15.0)

        # Invocación inmediata dentro del cooldown
        await self.cog.slash_resumir.callback(self.cog, interaction, limit=25, estilo="dalet")
        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        self.assertIn("Este canal ya fue resumido hace poco", args[0])
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_slash_resumir_success_flow(self):
        """Verifica que /resumir lea el historial de Discord, formatee los mensajes e invoque al NLP service."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 999999
        interaction.id = 111
        interaction.user.display_name = "Juan"
        interaction.guild = MagicMock()
        interaction.guild.icon = None
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        # Simular 5 mensajes en el historial de Discord
        mock_messages = []
        for i in range(5):
            msg = MagicMock(spec=discord.Message)
            msg.id = 200 + i
            msg.author.display_name = f"User{i}"
            msg.author.name = f"user{i}"
            msg.clean_content = f"Mensaje número {i}"
            msg.attachments = []
            msg.embeds = []
            mock_messages.append(msg)

        def async_history(limit=30):
            class AsyncIterator:
                def __init__(self, items):
                    self.items = list(items)
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    if not self.items:
                        raise StopAsyncIteration
                    return self.items.pop(0)
            return AsyncIterator(mock_messages)

        mock_channel = MagicMock()
        mock_channel.history = async_history
        mock_channel.name = "chat-general"
        interaction.channel = mock_channel

        await self.cog.slash_resumir.callback(self.cog, interaction, limit=25, estilo="dalet")

        # Debe llamar a nlp_service.generate_reply
        self.bot.nlp_service.generate_reply.assert_called_once()
        call_args = self.bot.nlp_service.generate_reply.call_args
        prompt_text = call_args[0][0]
        system_override = call_args[1].get("system_prompt_override", "")

        # Verificar que el prompt contenga el historial y el system prompt use la personalidad de Dalet
        self.assertIn("User0: Mensaje número 0", prompt_text)
        self.assertIn("User4: Mensaje número 4", prompt_text)
        self.assertIn("Eres Dalet", system_override)
        self.assertIn("El veredicto de Dalet", system_override)

        # Debe responder con un embed en followup
        interaction.followup.send.assert_called_once()
        sent_embed = interaction.followup.send.call_args[1].get("embed")
        self.assertIsNotNone(sent_embed)
        self.assertIn("Modo Dalet", sent_embed.title)


if __name__ == "__main__":
    unittest.main()
