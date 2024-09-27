from discord.ui import Button, View
import discord

class TargetSelectionView(View):
    def __init__(self, targets):
        super().__init__()
        self.selected_targets = set()  # 선택된 대상을 추적
        self.targets = targets

        # 각 대상에 대한 버튼 생성
        for target in targets:
            button = Button(label=target, style=discord.ButtonStyle.primary)
            button.callback = self.create_button_callback(target)
            self.add_item(button)

        # 완료 버튼 추가
        complete_button = Button(label="완료", style=discord.ButtonStyle.success)
        complete_button.callback = self.complete_selection
        self.add_item(complete_button)

    def create_button_callback(self, target):
        async def callback(interaction):
            if target in self.selected_targets:
                self.selected_targets.remove(target)
                await interaction.response.edit_message(content=f"{target} 선택 해제됨.", view=self)
            else:
                self.selected_targets.add(target)
                await interaction.response.edit_message(content=f"{target} 선택됨.", view=self)
        return callback

    async def complete_selection(self, interaction):
        # 선택 완료 시 처리할 로직
        await interaction.response.edit_message(content="완료", view=self)
        self.stop()  # View를 종료하여 더 이상 상호작용을 받지 않음