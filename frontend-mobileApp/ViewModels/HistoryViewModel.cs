using SalesMobileApp.Core;
using SalesMobileApp.Models;
using SalesMobileApp.Services;
namespace SalesMobileApp.ViewModels;
public sealed class HistoryViewModel : ObservableObject
{
    private readonly ApiClient _api; private readonly SessionStore _session; private List<SalesHistoryRow> _items = []; private string _error = ""; private bool _isBusy;
    public List<SalesHistoryRow> Items { get => _items; private set { SetProperty(ref _items, value); OnPropertyChanged(nameof(HasItems)); } } public string Error { get => _error; private set => SetProperty(ref _error, value); } public bool HasItems => Items.Count > 0;
    public bool IsBusy { get => _isBusy; private set { SetProperty(ref _isBusy, value); RefreshCommand.RaiseCanExecuteChanged(); } } public AsyncCommand RefreshCommand { get; }
    public HistoryViewModel(ApiClient api, SessionStore session) { _api = api; _session = session; RefreshCommand = new(LoadAsync, () => !IsBusy); }
    public async Task LoadAsync() { IsBusy = true; Error = ""; try { var id = await _session.GetUserIdAsync(); if (id is null) { await Shell.Current.GoToAsync("//login"); return; } Items = await _api.GetHistoryAsync(id.Value); } catch (Exception ex) { Error = ex is HttpRequestException ? "Không thể tải lịch sử." : ex.Message; } finally { IsBusy = false; } }
}
