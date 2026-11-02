from config import RU

def compute_advice(state):
    try:
        L, B = state["live"], state["blank"]
        me, mx = state["me"], state["maxhp"]
        four = state["mode"] == "4 игрока"
        act, ti = state["active"], state["target"]
        hp = state["opp_hp"]
        cnt = state["opp_n"]
        opp_det = state["opp_det"]
        
        tg = hp[ti]
        cuffed = state["cuffed"][ti]
        has = lambda n: state["my_items"].get(n, 0) > 0
    except (KeyError, IndexError):
        return "Ошибка данных для расчета стратегии."

    who = f"игрока {ti + 2}" if four else "соперника"
    weak = min(act, key=lambda i: (hp[i], i)) if act else 0
    
    if L + B == 0:
        return "Патронов нет. Ожидайте нового раунда или введите вручную."
        
    k = state["cur_known"]
    pos = f"[патрон №{state['spent'] + 1}] "
    
    if L == 0:
        return pos + "Боевых не осталось: стреляйте в СЕБЯ, это безопасно."
    if B == 0:
        return pos + f"Остались только боевые: выстрел в {who.upper()}."

    saw_ok = has("saw") and not state["sawed"] and tg > 1 and (four or tg >= 3)
    p = L / (L + B) if k is None else (1.0 if k == "live" else 0.0)
    src = " (телефон)" if (k and not state["is_known_direct"]) else ""

    if k is None and has("magnifier"):
        return pos + "Рекомендация: Использовать ЛУПУ."
        
    mine = sum(state["my_items"].values()) - (1 if has("mirror") else 0)
    if has("mirror") and cnt:
        bi = max(cnt, key=cnt.get)
        if cnt[bi] > mine:
            whom = f"игроком {bi + 2}" if four else "соперником"
            return pos + f"ЗЕРКАЛО: обменять предметы с {whom} (у него {cnt[bi]}, у вас {mine})."
            
    if has("adrenaline"):
        st = _best_steal(act, k, p, has, me, opp_det)
        if st:
            w, i = st
            return pos + f"АДРЕНАЛИН: украсть {RU[w].upper()} у игрока {i + 2}."

    if me <= 2 and has("potion") and me < mx and (four or me >= 2):
        return pos + "Выпить ЗЕЛЬЕ (+1 HP)."
        
    vd = state["voodoo_on"]
    if has("voodoo") and not vd and k != "blank":
        vt = f"игрока {weak + 2}" if four else "соперника"
        kill = " При 1 HP он умрёт от перенаправленного удара." if hp[weak] <= 1 else ""
        return pos + f"ВУДУ на {vt}: выстрел в себя станет безопасным.{kill}"
        
    if vd and k != "live":
        kill = f" Боевой убьёт игрока с малым HP ({hp[weak]})." if hp[weak] <= (2 if state["sawed"] and four else 1) else ""
        return pos + f"ВУДУ активно: выстрел в СЕБЯ безопасен. После боевого снимется."
        
    if k == "blank" and has("inverter"):
        return pos + f"ИНВЕРТОР: холостой станет боевым{src}, выстрел в {who.upper()}."
        
    if p >= 0.5:
        if has("handcuffs") and not cuffed:
            return pos + f"Надеть НАРУЧНИКИ на {who}, затем стрелять."
        if k == "live" and saw_ok:
            return pos + f"Использовать НОЖОВКУ, затем выстрел в {who.upper()} (x2 урон){src}."
        return pos + f"Выстрел в {who.upper()} (HP {tg}, шанс боевого {p:.0%}){src}."
        
    if has("soda") and p > 0.3 and k is None:
        return pos + f"ГАЗИРОВКА: сбросить текущий патрон (шанс боевого {p:.0%})."
        
    return pos + f"Выстрел в СЕБЯ (шанс боевого {p:.0%}){src}. Локальный ход сохранится."

def _best_steal(act, k, p, has, me, opp_det):
    wants = []
    if k is None and not has("magnifier"): wants.append("magnifier")
    if k == "blank" and not has("inverter"): wants.append("inverter")
    if p >= 0.5 and not has("handcuffs"): wants.append("handcuffs")
    if p >= 0.5 and not has("saw"): wants.append("saw")
    if me <= 2 and not has("potion"): wants.append("potion")
    
    for w in wants:
        for i in act:
            if opp_det[i].get(w, 0) > 0:
                return w, i
    return None
