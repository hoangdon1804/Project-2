using System.Text.Json;
namespace SalesMobileApp.Services;
public sealed class BackendSettings
{
    public string Windows { get; set; } = ""; public string AndroidEmulator { get; set; } = ""; public string AndroidDevice { get; set; } = ""; public string Production { get; set; } = "";
    public static async Task<BackendSettings> LoadAsync() { try { await using var stream = await FileSystem.OpenAppPackageFileAsync("backend-settings.json"); return await JsonSerializer.DeserializeAsync<BackendSettings>(stream) ?? new(); } catch { return new(); } }
}
