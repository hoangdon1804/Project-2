namespace SalesMobileApp.Services;
public sealed class SessionStore
{
    private const string TokenKey = "sales_jwt"; private const string UserIdKey = "sales_user_id";
    public Task<string?> GetTokenAsync() => SecureStorage.Default.GetAsync(TokenKey);
    public async Task<int?> GetUserIdAsync() { var value = await SecureStorage.Default.GetAsync(UserIdKey); return int.TryParse(value, out var id) ? id : null; }
    public async Task SaveAsync(string token, int userId) { await SecureStorage.Default.SetAsync(TokenKey, token); await SecureStorage.Default.SetAsync(UserIdKey, userId.ToString()); }
    public void Clear() { SecureStorage.Default.Remove(TokenKey); SecureStorage.Default.Remove(UserIdKey); }
}
