using SalesMobileApp.Core;
using SalesMobileApp.Models;
using SalesMobileApp.Services;
namespace SalesMobileApp.ViewModels;
public sealed class ProfileViewModel : ObservableObject
{
    private readonly ApiClient _api; private readonly SessionStore _session; private SalesProfile _profile = new(); private string _error = "", _message = ""; private bool _isBusy;
    public SalesProfile Profile { get => _profile; private set { SetProperty(ref _profile, value); OnPropertyChanged(nameof(FullName)); OnPropertyChanged(nameof(Email)); OnPropertyChanged(nameof(Phone)); } } public string FullName { get => Profile.full_name ?? ""; set { Profile.full_name = value; OnPropertyChanged(); } } public string Email { get => Profile.email; set { Profile.email = value; OnPropertyChanged(); } } public string Phone { get => Profile.phone ?? ""; set { Profile.phone = value; OnPropertyChanged(); } }
    public string Error { get => _error; private set => SetProperty(ref _error, value); } public string Message { get => _message; private set => SetProperty(ref _message, value); } public bool IsBusy { get => _isBusy; private set { SetProperty(ref _isBusy, value); SaveCommand.RaiseCanExecuteChanged(); } } public AsyncCommand SaveCommand { get; }
    public ProfileViewModel(ApiClient api, SessionStore session) { _api = api; _session = session; SaveCommand = new(SaveAsync, () => !IsBusy); }
    public async Task LoadAsync() { IsBusy = true; Error = ""; try { var id = await _session.GetUserIdAsync(); if (id is null) { await Shell.Current.GoToAsync("//login"); return; } Profile = await _api.GetProfileAsync(id.Value); } catch (Exception ex) { Error = ex is HttpRequestException ? "Không thể tải hồ sơ." : ex.Message; } finally { IsBusy = false; } }
    private async Task SaveAsync() { Error = Message = ""; if (string.IsNullOrWhiteSpace(Email) || !Email.Contains('@')) { Error = "Email không hợp lệ."; return; } IsBusy = true; try { var id = await _session.GetUserIdAsync(); if (id is null) return; Profile = await _api.UpdateProfileAsync(id.Value, Profile); Message = "Đã lưu hồ sơ."; } catch (Exception ex) { Error = ex is HttpRequestException ? "Không thể lưu hồ sơ." : ex.Message; } finally { IsBusy = false; } }
}
