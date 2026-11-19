using SalesMobileApp.Core;
using SalesMobileApp.Services;
namespace SalesMobileApp.ViewModels;
public sealed class LoginViewModel : ObservableObject
{
    private readonly ApiClient _api; private readonly SessionStore _session; private string _username = "", _password = "", _baseUrl = "", _error = ""; private bool _isBusy;
    public string Username { get => _username; set => SetProperty(ref _username, value); } public string Password { get => _password; set => SetProperty(ref _password, value); } public string BaseUrl { get => _baseUrl; set => SetProperty(ref _baseUrl, value); } public string Error { get => _error; private set => SetProperty(ref _error, value); }
    public bool IsBusy { get => _isBusy; private set { SetProperty(ref _isBusy, value); LoginCommand.RaiseCanExecuteChanged(); } } public AsyncCommand LoginCommand { get; } public AsyncCommand UseSuggestedUrlCommand { get; }
    public LoginViewModel(ApiClient api, SessionStore session) { _api = api; _session = session; LoginCommand = new(LoginAsync, () => !IsBusy); UseSuggestedUrlCommand = new(LoadSuggestedUrlAsync); }
    public async Task LoadSuggestedUrlAsync() { var settings = await BackendSettings.LoadAsync(); BaseUrl = DeviceInfo.Platform == DevicePlatform.Android ? settings.AndroidEmulator : settings.Windows; }
    private async Task LoginAsync()
    {
        Error = ""; if (string.IsNullOrWhiteSpace(BaseUrl) || string.IsNullOrWhiteSpace(Username) || string.IsNullOrWhiteSpace(Password)) { Error = "Nhập URL backend, tài khoản và mật khẩu."; return; }
        IsBusy = true; try { _api.SetBaseUrl(BaseUrl); var result = await _api.LoginAsync(Username.Trim(), Password); if (result.role != "sales") { Error = "Tài khoản này không thuộc vai trò Sales."; return; } await _session.SaveAsync(result.token, result.id); await Shell.Current.GoToAsync("dashboard"); }
        catch (Exception ex) { Error = ex is HttpRequestException ? "Không kết nối được backend. Kiểm tra URL và mạng rồi thử lại." : ex.Message; } finally { IsBusy = false; }
    }
}
