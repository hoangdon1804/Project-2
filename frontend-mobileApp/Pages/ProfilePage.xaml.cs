using SalesMobileApp.Core; using SalesMobileApp.ViewModels;
namespace SalesMobileApp.Pages;
public partial class ProfilePage : ContentPage { private readonly ProfileViewModel _vm; public ProfilePage() { InitializeComponent(); _vm = new(ServiceLocator.Services.GetRequiredService<Services.ApiClient>(), ServiceLocator.Services.GetRequiredService<Services.SessionStore>()); BindingContext = _vm; } protected override async void OnAppearing() { base.OnAppearing(); await _vm.LoadAsync(); } }
