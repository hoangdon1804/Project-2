using SalesMobileApp.Core;
using SalesMobileApp.Models;
using SalesMobileApp.Services;
namespace SalesMobileApp.ViewModels;
public sealed class DashboardViewModel : ObservableObject
{
    private readonly ApiClient _api; private readonly SessionStore _session; private WorkShiftResponse? _shift; private string _error = ""; private bool _isBusy;
    public WorkShiftResponse? Shift { get => _shift; private set { SetProperty(ref _shift, value); OnPropertyChanged(nameof(HasShift)); OnPropertyChanged(nameof(HasZones)); } } public string Error { get => _error; private set => SetProperty(ref _error, value); } public bool HasShift => Shift?.has_shift == true; public bool HasZones => Shift?.zones?.Count > 0;
    public bool IsBusy { get => _isBusy; private set { SetProperty(ref _isBusy, value); RefreshCommand.RaiseCanExecuteChanged(); } } public AsyncCommand RefreshCommand { get; } public AsyncCommand OpenHistoryCommand { get; set; } = null!; public AsyncCommand OpenProfileCommand { get; set; } = null!; public AsyncCommand OpenInvoiceCommand { get; set; } = null!;
    public DashboardViewModel(ApiClient api, SessionStore session) { _api = api; _session = session; RefreshCommand = new(LoadAsync, () => !IsBusy); }
    public async Task LoadAsync() { IsBusy = true; Error = ""; try { var id = await _session.GetUserIdAsync(); if (id is null) { await Shell.Current.GoToAsync("//login"); return; } Shift = await _api.GetShiftAsync(id.Value); } catch (Exception ex) { Error = ex is HttpRequestException ? "Không thể tải ca làm việc. Kiểm tra kết nối backend." : ex.Message; } finally { IsBusy = false; } }
    public Task OpenHistoryAsync() => Shell.Current.GoToAsync("history"); public Task OpenProfileAsync() => Shell.Current.GoToAsync("profile");
}
