public class PlayerReadyMsg
{
    public int type;
    public string uid;
}

public class EnterBattleReq
{
    public string roomId;
    public int heroId;
    public int extraField;
}
