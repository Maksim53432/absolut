from robloxmemoryapi import RobloxGameClient

try:
    client = RobloxGameClient()
    print("Подключение к Roblox успешно")

    game = client.DataModel
    # Пробуем прочитать имя локального игрока
    player_name = game.Players.LocalPlayer.Name
    print(f"Имя игрока: {player_name}")

except Exception as e:
    print(f"Ошибка: {type(e).__name__}: {e}")