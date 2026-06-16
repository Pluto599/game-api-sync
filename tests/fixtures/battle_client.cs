public class PlayerReadyMsg
{
    public int type;
    public string uid;
}

/// <summary>请求进入战斗</summary>
public class EnterBattleReq
{
    public string roomId;
    public int heroId;
    public int extraField;
}
